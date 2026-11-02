"""Leak audit for every public lifecycle document (M8). A document that fails is never served or written to a dataset.

Checks, recursively over every key and string:
  forbidden keys      private oracle fields and secrets (expected answers, criteria truths, evidence texts and required page paths, ledgers,
                      authorisation records, credentials) may not appear as keys at any depth
  forbidden patterns  loopback addresses with ports, absolute local paths, the private data directory, bearer tokens, API-key-like strings,
                      the provider key variable
  expected answers    with the answers given (server-side, from the store's private outcomes), no expected answer may appear in any string OUTSIDE
                      the agent's own recorded output and observed site content (the AGENT_FIELDS keys: the agent's answer, its stated memory,
                      goals and assessments, its action targets, page titles and visited paths). Those are run evidence, as the hosted product
                      already shows them; everything the oracle knows that the agent did not produce is withheld."""
from __future__ import annotations

import re

FORBIDDEN_KEYS = frozenset({"truth", "expected", "expected_answer", "correct_answer", "solution", "evidence_texts", "evidence_paths", "missing_evidence",
                            "variant_criteria", "private", "private_outcome", "ledger", "ledger_dir", "authorization", "authorization_sha256", "instruction",
                            "approval_note", "api_key", "operator_token", "token", "password", "secret", "out_dir", "trial_dir", "messages", "raw_response"})
AGENT_FIELDS = frozenset({"answer", "answers", "memory", "goal", "assessment", "target", "title", "visits", "path", "current"})
PATTERNS = [(re.compile(r"(?:127\.0\.0\.1|localhost|\[::1\]):\d{2,5}"), "loopback address with port"),
            (re.compile(r"/home/[A-Za-z0-9_.-]+|/root/|[A-Z]:\\\\Users"), "absolute local path"),
            (re.compile(r"scanner-data"), "private data directory"),
            (re.compile(r"\bBearer\s+[A-Za-z0-9._-]{8,}"), "bearer token"),
            (re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"), "API-key-like string"),
            (re.compile(r"META_MODEL_API_KEY\s*="), "provider key assignment")]


def _contains(text: str, answer: str) -> bool:
    return bool(re.search(rf"(?<![\w$]){re.escape(answer)}(?!\w)", text)) if len(answer) >= 4 else f'"{answer}"' in text


def check(doc, answers: list[str] | None = None, *, where: str = "document", exempt_agent: bool = True) -> list[str]:
    """Every violation (empty = clean). `answers`: expected answers to search for (None = structural and pattern checks only)."""
    problems: list[str] = []
    answers = sorted({a for a in (answers or []) if isinstance(a, str) and a.strip()})

    def walk(x, path: str, agent: bool):
        if isinstance(x, dict):
            for k, v in x.items():
                kl = str(k).lower()
                if kl in FORBIDDEN_KEYS:
                    problems.append(f"{where}{path}: forbidden key {k!r}")
                    continue
                walk(v, f"{path}.{k}", agent or (exempt_agent and kl in AGENT_FIELDS))
        elif isinstance(x, (list, tuple)):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]", agent)
        elif isinstance(x, str):
            for rx, what in PATTERNS:
                if rx.search(x):
                    problems.append(f"{where}{path}: {what}")
            if not agent:
                hit = [a for a in answers if _contains(x, a)]
                if hit:
                    problems.append(f"{where}{path}: contains an expected answer ({len(hit)})")
    walk(doc, "", False)
    return problems


def check_evaluation(doc: dict, answers_by_task: dict[str, list[str]] | None, *, where: str = "evaluation") -> list[str]:
    """An evaluation document: each task's own wording is checked against ITS OWN answers (a task may name an item that answers another task, as
    the store's audit allows); everything else against every answer, with the agent's own output exempt (see `check`)."""
    every = sorted({a for v in (answers_by_task or {}).values() for a in v})
    rest = {k: v for k, v in doc.items() if k != "tasks"}
    exempt = doc.get("mode") == "paid"                                         # a rehearsal's stand-in "agent" output is derived from the answers
    problems = check(rest, every if answers_by_task is not None else None, where=where, exempt_agent=exempt)
    for i, t in enumerate(doc.get("tasks") or []):
        own = (answers_by_task or {}).get(t.get("task_id"), []) if answers_by_task is not None else None
        problems += check(t, own, where=f"{where}.tasks[{i}]")
    return problems
