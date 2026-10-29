"""Bounded, sanitized capture of model HTTP exchanges, taken before Browser Use parses the response.

The Browser Use adapter parses and validates model output inside ``ainvoke``. If that raises, the raw
content, finish reason, request id and usage are otherwise lost. These httpx event hooks record them first.
Nothing here changes what is sent to, or accepted from, the provider.
"""
import hashlib
import re
import json
import time

from .recorder import Recorder, utcnow

MAX_CONTENT_CHARS = 20_000       # raw model content kept per response
MAX_ERROR_BODY_CHARS = 2_000     # non-200 bodies
MAX_JSON_PROBES = 20             # '{' positions tried when looking for embedded JSON
# Complete strict AgentOutput schema for the reference tool set under browser-use 0.11.13 (pinned by a test).
FULL_AGENT_SCHEMA_SHA256 = "c80ef8b813abef0b2afd79c83a6f31e857c0101ea8730952ee78d61e65f9a194"
LAST_STEP_MARKERS = ("this is your last step", 'only tool available is the "done" tool')
# Browser Use's final-step state (AgentStepInfo.is_last_step): the response schema narrows to `done` only and one
# exact context message is appended. Pinned against the installed library by tests (drift fails there).
DONE_ONLY_SCHEMA_SHA256 = "7964acb55bed223f00dc3de611c026b455f264a00c21cabf5e127b8e10025dc1"
LAST_STEP_NOTICE = ('You reached max_steps - this is your last step. Your only tool available is the "done" tool. '
                    'No other tool is available. All other tools which you see in history or examples are not available.\n'
                    'If the task is not yet fully finished as requested by the user, set success in "done" to false! '
                    'E.g. if not all steps are fully completed. Else success to true.\n'
                    'Include everything you found out for the ultimate task in the done text.')
# The failure-forced done state is disabled by the frozen profile (final_response_after_failure=False); seeing it is a
# deviation, never an expected state.
FORCED_DONE_MARKER = "therefore we terminate the agent"
STEP_LABEL = re.compile(r"Step(\d+) maximum:(\d+)")
MIN_SYSTEM_PROMPT_CHARS = 20_000
# Published muse-spark-1.3 pay-as-you-go prices, USD per 1M tokens (currency not named by the provider).
PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M = 1.25, 4.25
IMAGE_TOKENS_ESTIMATE = 1_430    # calibrated: 8,128 measured prompt tokens vs ~26.8k text chars + one 1280x960 PNG
CHARS_PER_TOKEN = 4
# The response_format schema is billed as input: the 7,915-byte full schema added ~1,300 measured prompt tokens
# over the 1,274-byte done-only schema (≈5 bytes/token). Count it at 4 bytes/token (≈25% conservative) and add a
# 10% margin over the whole input estimate. Calibration points (measured prompt tokens): 8,128 (done-only schema)
# and 9,443 (full schema); both are covered by the estimator (tests).
SCHEMA_BYTES_PER_TOKEN = 4
INPUT_SAFETY_MARGIN = 1.10


class FidelityViolation(RuntimeError):
    """A diagnostic request does not match the experiment definition; it is blocked before the network."""


class GateRefused(RuntimeError):
    """A request gate (durable ledger) refused to reserve spend for this request."""


class EstimatedCostLimit(FidelityViolation):
    """Sending this request would push the cumulative estimated spend over the cap; blocked before the network."""


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def request_summary(body: dict) -> dict:
    """Structure of a chat-completions request without message text or image bytes."""
    messages = []
    for message in body.get("messages") or []:
        content = message.get("content")
        if isinstance(content, str):
            parts = [{"type": "text", "chars": len(content)}]
        else:
            parts = []
            for part in content or []:
                if part.get("type") == "text":
                    parts.append({"type": "text", "chars": len(part.get("text", ""))})
                elif part.get("type") == "image_url":
                    image = part.get("image_url") or {}
                    parts.append({"type": "image_url", "detail": image.get("detail"),
                                  "url_chars": len(image.get("url", "")),
                                  "data_url": str(image.get("url", "")).startswith("data:image/")})
                else:
                    parts.append({"type": part.get("type")})
        messages.append({"role": message.get("role"), "parts": parts})
    fmt = body.get("response_format") or {}
    schema_info = None
    if fmt:
        spec = fmt.get("json_schema") or {}
        schema = spec.get("schema")
        schema_info = {"type": fmt.get("type"), "name": spec.get("name"), "strict": spec.get("strict"),
                       "schema_sha256": _sha(schema) if schema is not None else None,
                       "schema_canonical_bytes": len(json.dumps(schema, sort_keys=True, separators=(",", ":")))
                       if schema is not None else None}
    scalars = {k: v for k, v in body.items() if k not in {"messages", "response_format"}}
    return {"body_keys": sorted(body), "model": body.get("model"), "parameters": scalars,
            "response_format": schema_info, "messages": messages}


def message_texts(body: dict) -> tuple[str, str, int]:
    """(system text, user text, image count) of a chat-completions body."""
    system, user, images = [], [], 0
    for message in body.get("messages") or []:
        content = message.get("content")
        parts = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
        for part in parts:
            if part.get("type") == "text":
                (system if message.get("role") == "system" else user).append(part.get("text", ""))
            elif part.get("type") == "image_url":
                images += 1
    return "\n".join(system), "\n".join(user), images


def estimate_cost_usd(body: dict) -> dict:
    """Upper-bound cost of one request: estimated input tokens plus the full completion cap (calculated)."""
    system, user, images = message_texts(body)
    schema = ((body.get("response_format") or {}).get("json_schema") or {}).get("schema")
    schema_bytes = len(json.dumps(schema, sort_keys=True, separators=(",", ":"))) if schema is not None else 0
    input_tokens = round(((len(system) + len(user)) / CHARS_PER_TOKEN + images * IMAGE_TOKENS_ESTIMATE
                          + schema_bytes / SCHEMA_BYTES_PER_TOKEN) * INPUT_SAFETY_MARGIN)
    output_tokens = body.get("max_completion_tokens") or 0
    usd = input_tokens * PRICE_INPUT_PER_M / 1e6 + output_tokens * PRICE_OUTPUT_PER_M / 1e6
    return {"input_tokens_estimate": input_tokens, "output_tokens_cap": output_tokens, "schema_bytes": schema_bytes,
            "usd": round(usd, 5)}


def budget_notice(steps_used: int, max_steps: int) -> str:
    """Browser Use's advance-notice message for steps at >= 75% of the budget that are not the last step."""
    pct = int(steps_used / max_steps * 100)
    return (f"BUDGET WARNING: You have used {steps_used}/{max_steps} steps ({pct}%). {max_steps - steps_used} steps remaining. "
            "If the task cannot be completed in the remaining steps, prioritize: (1) consolidate your results (save to files "
            "if the file system is in use), (2) call done with what you have. "
            "Partial results are far more valuable than exhausting all steps with nothing saved.")


def standalone_messages(body: dict) -> list[str]:
    """Texts of user messages that consist of a single text part (how Browser Use delivers its context notices)."""
    found = []
    for message in body.get("messages") or []:
        content = message.get("content")
        if message.get("role") == "user" and isinstance(content, list) and len(content) == 1 and content[0].get("type") == "text":
            found.append(content[0].get("text", ""))
        elif message.get("role") == "user" and isinstance(content, str):
            found.append(content)
    return found


def classify_step_state(user: str, max_steps: int, request_index: int, standalone: list[str] | None = None) -> tuple[str | None, list[str]]:
    """('normal' | 'final' | None, problems). Validates the step label and the exact framework notices for that state.

    Only two states exist in the frozen run: an ordinary step (full schema, optional exact budget notice) and the
    final step (done-only schema plus exactly the last-step notice). The first request can never be the final step."""
    labels = STEP_LABEL.findall(user)
    if len(labels) != 1:
        return None, [f"expected exactly one 'Step<n> maximum:<m>' label, found {len(labels)}"]
    step, maximum = int(labels[0][0]), int(labels[0][1])
    if maximum != max_steps or not 1 <= step <= max_steps:
        return None, [f"step label Step{step} maximum:{maximum} inconsistent with max_steps={max_steps}"]
    problems = []
    lowered = user.lower()
    standalone = standalone or []
    if FORCED_DONE_MARKER in lowered:
        problems.append("failure-forced done notice present (disabled in the frozen profile)")
    final = step == max_steps
    if final:
        if request_index < 2:
            problems.append("the first request cannot be the final step (done-only schema not accepted)")
        if user.count(LAST_STEP_NOTICE) != 1 or standalone.count(LAST_STEP_NOTICE) != 1 or "this is your last step" not in lowered \
                or lowered.count("this is your last step") != 1:
            problems.append("final step lacks exactly one verbatim standalone last-step notice")
        if "budget warning" in lowered:
            problems.append("budget warning present on the final step")
    else:
        if any(marker in lowered for marker in LAST_STEP_MARKERS):
            problems.append("last-step instruction present before the final step")
        expected = budget_notice(step, max_steps) if step / max_steps >= 0.75 else None
        count = lowered.count("budget warning")
        if expected is None and count:
            problems.append("unexpected budget warning")
        elif expected is not None and (count != 1 or user.count(expected) != 1 or standalone.count(expected) != 1):
            problems.append("budget warning missing or not the verbatim notice for this step")
    return ("final" if final else "normal"), problems


def check_fidelity(body: dict, expectations: dict, request_index: int = 1) -> list[str]:
    """Violations of the experiment definition in an outgoing request (empty list = faithful).

    With ``expectations['max_steps']`` the check is step-aware (see ``classify_step_state``); without it every request
    must carry the full schema and no last-step text."""
    problems = []
    fmt = body.get("response_format") or {}
    spec = fmt.get("json_schema") or {}
    sha = _sha(spec.get("schema")) if spec.get("schema") is not None else None
    system, user, images = message_texts(body)
    state, step_problems = (None, [])
    max_steps = expectations.get("max_steps")
    if max_steps:
        state, step_problems = classify_step_state(user, max_steps, request_index, standalone_messages(body))
    expected_sha = expectations.get("schema_sha256")
    if state == "final" and not step_problems:
        done_only = expectations.get("done_only_schema_sha256") or DONE_ONLY_SCHEMA_SHA256      # per-task answer models have their own done-only schema
        if sha != done_only:
            problems.append(f"final-step schema sha256 {sha} != known done-only schema {done_only}")
    elif expected_sha and sha != expected_sha:
        problems.append(f"response_format schema sha256 {sha} != expected {expected_sha} (schema narrowed or changed)")
    problems.extend(step_problems)
    if fmt.get("type") != "json_schema" or spec.get("strict") is not True or spec.get("name") != "agent_output":
        problems.append("response_format is not the strict json_schema agent_output")
    for key, expected in (expectations.get("parameters") or {}).items():
        if body.get(key) != expected:
            problems.append(f"parameter {key}={body.get(key)!r}, expected {expected!r}")
    if len(system) < MIN_SYSTEM_PROMPT_CHARS:
        problems.append(f"system prompt has {len(system)} chars (< {MIN_SYSTEM_PROMPT_CHARS})")
    if images != 1:
        problems.append(f"expected exactly one screenshot, found {images}")
    for marker, label in (("<browser_state>", "DOM state"), ("Agent initialized", "first-step history")):
        if marker not in user:
            problems.append(f"user context lacks {label} ({marker!r})")
    task_prompt = expectations.get("task_prompt")
    if task_prompt and task_prompt not in user:
        problems.append("public task prompt not present in the user context")
    if not max_steps:
        lowered = (system + "\n" + user).lower()
        for marker in LAST_STEP_MARKERS:
            if marker in lowered:
                problems.append(f"last-step instruction present ({marker!r})")
    elif any(marker in system.lower() for marker in LAST_STEP_MARKERS):
        problems.append("last-step instruction present in the system prompt")
    ceiling = expectations.get("max_estimated_cost_usd")
    if ceiling is not None:
        estimate = estimate_cost_usd(body)
        if estimate["usd"] >= ceiling:
            problems.append(f"estimated worst-case cost US${estimate['usd']} >= US${ceiling}")
    return problems


def analyze_content(content) -> dict:
    """Facts about the returned text, independent of any output model."""
    if content is None:
        return {"kind": "null"}
    if not isinstance(content, str):
        return {"kind": "non_string", "python_type": type(content).__name__}
    try:
        json.loads(content)
        return {"kind": "json", "chars": len(content)}
    except ValueError:
        pass
    info = {"kind": "non_json", "chars": len(content), "starts_with_brace": content.lstrip().startswith("{"),
            "ends_with_brace": content.rstrip().endswith("}"), "embedded_json": None}
    decoder = json.JSONDecoder()
    probes = 0
    for start, char in enumerate(content):
        if char != "{":
            continue
        probes += 1
        if probes > MAX_JSON_PROBES:
            break
        try:
            value, end = decoder.raw_decode(content, start)
        except ValueError:
            continue
        info["embedded_json"] = {"offset": start, "chars": end - start, "trailing_chars": len(content) - end,
                                 "is_object": isinstance(value, dict)}
        break
    return info


class ResponseCapture:
    """httpx event hooks writing ``model_http_request``/``model_http_response`` events and a response file."""

    def __init__(self, recorder: Recorder, expectations: dict | None = None):
        self.recorder = recorder
        self.expectations = expectations
        self.violations: list[str] = []
        self.cost_blocks: list[str] = []
        self.last_block = None            # 'fidelity' | 'cost' | None, for the most recent request
        self.estimated_sent_usd = 0.0     # sum of worst-case estimates of requests that were allowed onto the network
        self.requests: list[dict] = []
        self.records: list[dict] = []
        self.gate = getattr(recorder, "request_gate", None)   # optional durable per-request spend gate (WebArena live path); None for every other run
        self._started: list[float] = []
        self._claimed = 0

    def attach(self, client):
        client.event_hooks["request"].append(self.on_request)
        client.event_hooks["response"].append(self.on_response)
        return client

    async def on_request(self, request):
        self._started.append(time.monotonic())
        try:
            body = json.loads(request.content)
        except ValueError:
            body = {}
        summary = request_summary(body)
        index = len(self._started)
        schema_sha = (summary["response_format"] or {}).get("schema_sha256")
        fidelity = {"schema_sha256": schema_sha, "schema_narrowed": schema_sha != ((self.expectations or {}).get("schema_sha256") or FULL_AGENT_SCHEMA_SHA256)}
        problems = check_fidelity(body, self.expectations, index) if self.expectations else []
        cost_problem = None
        if self.expectations:
            estimate = estimate_cost_usd(body)
            fidelity["estimate"] = estimate
            fidelity["violations"] = problems
            cap = self.expectations.get("max_cumulative_estimated_cost_usd")
            if cap is not None and not problems and self.estimated_sent_usd + estimate["usd"] > cap:
                cost_problem = (f"cumulative estimated cost US${round(self.estimated_sent_usd + estimate['usd'], 5)} "
                                f"(sent US${round(self.estimated_sent_usd, 5)} + this request US${estimate['usd']}, "
                                f"full {estimate['output_tokens_cap']}-token allowance) > cap US${cap}")
            fidelity["cumulative_estimated_before_usd"] = round(self.estimated_sent_usd, 5)
            if cost_problem:
                fidelity["cost_limit"] = cost_problem
        if self.gate is not None and not problems and not cost_problem:
            try:
                fidelity["reservation"] = self.gate.reserve(index, body, fidelity.get("estimate"))     # durable BEFORE the network
            except GateRefused as exc:
                cost_problem = str(exc)
                fidelity["cost_limit"] = cost_problem
        blocked = bool(problems or cost_problem)
        self.last_block = "fidelity" if problems else "cost" if cost_problem else None
        fidelity["blocked_before_network"] = blocked
        if not blocked and self.expectations:
            self.estimated_sent_usd += fidelity["estimate"]["usd"]
        self.requests.append(fidelity)
        self.recorder.event("model_http_request", index=index, method=request.method,
                            url=str(request.url.copy_with(query=None)),
                            timeout=dict(request.extensions.get("timeout") or {}), fidelity=fidelity, **summary)
        if problems:  # raised before the transport: nothing reaches the network
            self.violations.extend(problems)
            self.recorder.event("fidelity_violation", index=index, violations=problems)
            raise FidelityViolation("; ".join(problems))
        if cost_problem:
            self.cost_blocks.append(cost_problem)
            self.recorder.event("estimated_cost_limit", index=index, detail=cost_problem)
            raise EstimatedCostLimit(cost_problem)

    def cost_summary(self) -> dict | None:
        if not self.expectations:
            return None
        return {"per_request_ceiling_usd": self.expectations.get("max_estimated_cost_usd"),
                "cumulative_cap_usd": self.expectations.get("max_cumulative_estimated_cost_usd"),
                "cumulative_estimated_sent_usd": round(self.estimated_sent_usd, 5),
                "requests_sent_to_network": sum(1 for r in self.requests if not r.get("blocked_before_network")),
                "requests_blocked_before_network": sum(1 for r in self.requests if r.get("blocked_before_network")),
                "basis": "calculated worst case: estimated input + full max_completion_tokens at published prices; "
                         "not provider-reported"}

    async def on_response(self, response):
        index = len(self.records) + 1
        await response.aread()
        started = self._started[index - 1] if index - 1 < len(self._started) else None
        record = {"index": index, "captured_at": utcnow(), "http_status": response.status_code,
                  "request_id": response.headers.get("x-request-id") or response.headers.get("request-id"),
                  "elapsed_seconds": round(time.monotonic() - started, 3) if started else None,
                  "body_bytes": len(response.content)}
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code == 200 and isinstance(payload, dict):
            choice = (payload.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content")
            usage = payload.get("usage")
            details = (usage or {}).get("completion_tokens_details") or {}
            record.update(
                response_model=payload.get("model"), finish_reason=choice.get("finish_reason"),
                refusal=message.get("refusal"), usage=usage,
                prompt_tokens=(usage or {}).get("prompt_tokens"),
                completion_tokens=(usage or {}).get("completion_tokens"),
                reasoning_tokens=details.get("reasoning_tokens"),
                content_analysis=analyze_content(content),
                content=content if not isinstance(content, str) else content[:MAX_CONTENT_CHARS],
                content_truncated=isinstance(content, str) and len(content) > MAX_CONTENT_CHARS)
        else:
            record["error_body"] = (payload if payload is not None else response.text[:MAX_ERROR_BODY_CHARS])
        self.records.append(record)
        if self.gate is not None:
            sent = [i + 1 for i, r in enumerate(self.requests) if not r.get("blocked_before_network")]
            record["settlement"] = self.gate.settle(sent[index - 1] if index - 1 < len(sent) else index, record)     # request index (blocked requests have no response)
        self.recorder.write(f"model-response-{index:02d}.json", record)
        summary = {k: v for k, v in record.items() if k not in {"content", "error_body"}}
        self.recorder.event("model_http_response", file=f"model-response-{index:02d}.json", **summary)

    def take(self) -> list[dict]:
        """Records captured since the previous call (one per model invocation; SDK retries are off)."""
        fresh = self.records[self._claimed:]
        self._claimed = len(self.records)
        return fresh

    def summary(self) -> list[dict]:
        keys = ("index", "http_status", "request_id", "finish_reason", "prompt_tokens", "completion_tokens",
                "reasoning_tokens", "elapsed_seconds", "content_analysis", "output_error",
                "raw_protocol_compliant", "recovered_action_valid")
        rows = [{k: r.get(k) for k in keys if k in r} for r in self.records]
        for row, record in zip(rows, self.records):
            if record.get("recovery"):
                row["recovery"] = {k: record["recovery"].get(k) for k in ("parser", "status", "reason", "validated")}
        sent = [r for r in self.requests if not r.get("blocked_before_network")]
        for row in rows:  # merge the outgoing-request facts (schema hash, narrowing flag) by index
            if row["index"] - 1 < len(sent):  # blocked requests never produce a response record
                row.update({k: v for k, v in sent[row["index"] - 1].items() if k in ("schema_sha256", "schema_narrowed")})
        return rows


def attach_capture(llm, recorder: Recorder):
    """Add capture hooks to the model's httpx client; return None for models without one.

    ``recorder.expectations`` (set by the runner for diagnostic runs) turns on pre-send fidelity checks."""
    if not hasattr(llm, "http_client"):
        return None
    if llm.http_client is None:
        from openai import DefaultAsyncHttpxClient  # same defaults the SDK would have used
        llm.http_client = DefaultAsyncHttpxClient()
    capture = ResponseCapture(recorder, getattr(recorder, "expectations", None))
    capture.attach(llm.http_client)
    return capture


def classify_output(record: dict, output_format) -> dict | None:
    """Return a ``model_output_error`` description for a 200 response that cannot become the output model."""
    if record.get("http_status") != 200 or "content_analysis" not in record:
        return None
    analysis, finish = record["content_analysis"], record.get("finish_reason")
    if record.get("content_truncated"):
        return {"subtype": "unclassified_truncated_capture", "finish_reason": finish}
    if analysis["kind"] == "null":
        return {"subtype": "length_without_content" if finish == "length" else "null_content",
                "finish_reason": finish, "reasoning_tokens": record.get("reasoning_tokens"),
                "completion_tokens": record.get("completion_tokens")}
    if analysis["kind"] == "non_json":
        return {"subtype": "malformed_json", "finish_reason": finish,
                "starts_with_brace": analysis["starts_with_brace"], "embedded_json": analysis["embedded_json"]}
    if analysis["kind"] == "json" and output_format is not None:
        try:
            output_format.model_validate_json(record["content"])
        except Exception as exc:  # pydantic.ValidationError; input values are deliberately not recorded
            errors = exc.errors(include_input=False, include_url=False)[:20] if hasattr(exc, "errors") else []
            return {"subtype": "schema_validation", "finish_reason": finish,
                    "errors": [{"loc": [str(p) for p in e.get("loc", ())], "type": e.get("type")} for e in errors]}
    if finish == "length":
        return {"subtype": "truncated", "finish_reason": finish}
    return None
