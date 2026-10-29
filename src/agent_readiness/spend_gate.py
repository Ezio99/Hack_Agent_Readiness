"""Durable, per-request spend gate shared by every live path (WebArena runner, synthetic-suite scanner). Extracted unchanged from `webarena/live.py` (Task 014).

Every outgoing model HTTP request first passes the fidelity guard, then this gate: a conservative upper bound (estimated input incl. a generous screenshot allowance + the FULL
completion allowance, +10 % margin) is appended to the fsync'd ledger BEFORE the request can reach the network. The gate refuses (nothing sent) when the run cap, the ledger
ceiling, the request-count cap or the per-request cap would be exceeded, or after any bound violation. The reservation is replaced by the actual calculated cost only when the
provider returns usage that does not exceed the bound; timeouts, transport errors, non-200 responses and missing usage keep the FULL bound counted, also across restarts.
Calculated cost uses the verified published prices; the provider reports no cost, so figures are estimates and not a bill."""
from __future__ import annotations

from .capture import IMAGE_TOKENS_ESTIMATE, INPUT_SAFETY_MARGIN, PRICE_INPUT_PER_M, GateRefused, estimate_cost_usd, message_texts
from .scanner.live import Halt, Ledger, cost_of

PER_REQUEST_CAP_USD = 0.05
RUN_CAP_USD = 0.50
MAX_REQUESTS = 16
IMAGE_UPPER_BOUND_TOKENS = 4_000   # per screenshot; the calibrated estimate is 1,430 (measured 8,128/9,443 prompt tokens) -> ~2.8x headroom


def upper_bound_usd(body: dict) -> tuple[float, dict]:
    """Conservative upper bound of one request: the guard's estimate (full completion cap, schema, +10 %) plus extra screenshot headroom."""
    est = estimate_cost_usd(body)
    _s, _u, images = message_texts(body)
    extra_tokens = round(images * max(0, IMAGE_UPPER_BOUND_TOKENS - IMAGE_TOKENS_ESTIMATE) * INPUT_SAFETY_MARGIN)
    usd = round(est["usd"] + extra_tokens * PRICE_INPUT_PER_M / 1e6, 6)
    return usd, {**est, "images": images, "image_headroom_tokens": extra_tokens, "upper_bound_usd": usd}


class RequestGate:
    """Durable per-request spend gate (see module docstring). Plugged into `ResponseCapture` through `recorder.request_gate`."""

    def __init__(self, ledger: Ledger, run_id: str, *, run_cap: float = RUN_CAP_USD, per_request_cap: float = PER_REQUEST_CAP_USD, max_requests: int = MAX_REQUESTS):
        self.ledger, self.run_id, self.run_cap, self.per_request_cap, self.max_requests = ledger, run_id, run_cap, per_request_cap, max_requests
        self.violation: str | None = None
        self.log: list[dict] = []

    def _id(self, index: int) -> str:
        return f"{self.run_id}:req{index:02d}"

    def run_committed(self) -> float:
        state: dict[str, float] = {}
        for e in self.ledger.entries():
            if e["kind"] in ("reserve", "settle") and e["id"].startswith(self.run_id + ":req"):
                if e["kind"] == "reserve":
                    state.setdefault(e["id"], e["usd"])
                else:
                    state[e["id"]] = e["usd"]
        return round(sum(state.values()), 6)

    def request_count(self) -> int:
        return sum(1 for e in self.ledger.entries() if e["kind"] == "reserve" and e["id"].startswith(self.run_id + ":req"))

    def reserve(self, index: int, body: dict, estimate: dict | None = None) -> dict:
        if self.violation:
            raise GateRefused(f"gate closed after a bound violation: {self.violation}")
        usd, detail = upper_bound_usd(body)
        if usd > self.per_request_cap:
            raise GateRefused(f"upper bound US${usd} for this request exceeds the per-request cap US${self.per_request_cap}")
        if self.request_count() >= self.max_requests:
            raise GateRefused(f"request-count cap {self.max_requests} reached")
        if self.run_committed() + usd > self.run_cap + 1e-9:
            raise GateRefused(f"run cap US${self.run_cap}: committed US${self.run_committed()} + this request's upper bound US${usd}")
        try:
            self.ledger.reserve(self._id(index), usd)            # raises Halt over the ledger ceiling or on a repeated id; fsync'd before returning
        except Halt as exc:
            raise GateRefused(str(exc)) from exc
        self.log.append({"event": "reserved", "index": index, **detail})
        return detail

    def settle(self, index: int, record: dict) -> dict:
        reserved = next((e["usd"] for e in self.ledger.entries() if e["kind"] == "reserve" and e["id"] == self._id(index)), None)
        usage = record.get("usage") if record.get("http_status") == 200 else None
        if reserved is None:
            self.violation = f"response for request {index} without a reservation"
            return {"settled": False, "reason": self.violation}
        if not usage or usage.get("prompt_tokens") is None or usage.get("completion_tokens") is None:
            self.log.append({"event": "kept_full", "index": index, "usd": reserved})
            return {"settled": False, "reason": "no usage in the response; the full upper bound stays counted", "kept_usd": reserved}
        actual = cost_of(usage)
        if actual > reserved + 1e-9:
            self.violation = f"actual calculated cost US${actual} exceeded the reserved upper bound US${reserved} on request {index}"
            self.ledger.settle(self._id(index), actual)           # record the truth even though it exceeds the bound
            self.log.append({"event": "bound_violation", "index": index, "actual": actual, "reserved": reserved})
            return {"settled": True, "actual_usd": actual, "bound_violation": self.violation}
        self.ledger.settle(self._id(index), actual)
        self.log.append({"event": "settled", "index": index, "actual": actual, "reserved": reserved})
        return {"settled": True, "actual_usd": actual, "reserved_usd": reserved}

    def unsettled(self) -> list[str]:
        sett = {e["id"] for e in self.ledger.entries() if e["kind"] == "settle"}
        return [e["id"] for e in self.ledger.entries() if e["kind"] == "reserve" and e["id"].startswith(self.run_id + ":req") and e["id"] not in sett]


