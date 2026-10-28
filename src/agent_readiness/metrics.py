"""Harness-side run metrics derived from the trace and private truth (never visible to the agent).

Visiting a product page other than the target is reported as an objective count. It is *not* an error classification:
exploratory visits are legitimate behaviour, and only the independent evaluator decides task success."""
from collections import Counter
from urllib.parse import parse_qs, urlsplit
from .capture import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M
from .inventory import PRODUCTS

FILTER_KEYS = ("q", "category", "brand", "max_price")


def product_for_url(url: str):
    path = urlsplit(url).path
    if not path.startswith("/products/"):
        return None
    route = path[len("/products/"):].strip("/")
    return next((p for p in PRODUCTS if p.route == route), None)


def run_metrics(events: list[dict], record: dict, expected_product_id: str | None) -> dict:
    observations = [e for e in events if e.get("kind") == "observation"]
    arrivals, last_url = [], None
    for event in observations:
        url = event.get("url")
        if url == last_url:
            continue
        last_url = url
        product = product_for_url(url or "")
        if product is not None:
            arrivals.append({"step": event.get("step"), "product_id": product.product_id,
                             "is_target": product.product_id == expected_product_id})
    non_target = [a for a in arrivals if not a["is_target"]]
    actions = Counter()
    for event in observations:
        for action in event.get("proposed_actions") or []:
            actions.update(action.keys())
    filter_params = set()
    for event in observations:
        query = parse_qs(urlsplit(event.get("url") or "").query)
        filter_params.update(k for k in FILTER_KEYS if k in query)
    listing_views = sum(1 for e in observations if urlsplit(e.get("url") or "").path == "/")
    usage = [u for u in (record.get("usage") or []) if u]
    prompt = sum(u.get("prompt_tokens") or 0 for u in usage)
    completion = sum(u.get("completion_tokens") or 0 for u in usage)
    captures = record.get("http_captures") or []
    reasoning = sum(c.get("reasoning_tokens") or 0 for c in captures)
    latencies = [c.get("elapsed_seconds") for c in captures if c.get("elapsed_seconds") is not None]
    evaluation = record.get("evaluation") or {}
    return {
        "task_success": {"evaluator_passed": evaluation.get("passed"), "status": record.get("status")},
        "navigation": {
            "observed_steps": len(observations), "proposed_action_counts": dict(actions),
            "proposed_actions_total": sum(actions.values()),
            "listing_page_observations": listing_views,
            "product_page_arrivals": arrivals,
            "first_product_page_is_target": (arrivals[0]["is_target"] if arrivals else None),
            "target_page_reached": any(a["is_target"] for a in arrivals),
            "non_target_product_page_arrivals": len(non_target),
            "distinct_non_target_products": len({a["product_id"] for a in non_target}),
            "limitation": "pages are counted when observed at a step start; a page reached by the final action is not observed",
        },
        "strategy": {"search_or_filter_params_in_observed_urls": sorted(filter_params),
                     "used_search_or_filter": bool(filter_params)},
        "tokens": {"prompt": prompt, "completion": completion, "reasoning": reasoning, "requests_with_usage": len(usage)},
        "latency": {"model_request_seconds": round(sum(latencies), 3) if latencies else None,
                    "per_request_seconds": latencies, "run_elapsed_seconds": record.get("elapsed_seconds")},
        "cost": {"calculated_actual_usd": round(prompt * PRICE_INPUT_PER_M / 1e6 + completion * PRICE_OUTPUT_PER_M / 1e6, 6),
                 "estimated_worst_case_sent_usd": (record.get("estimated_cost") or {}).get("cumulative_estimated_sent_usd"),
                 "basis": "calculated from provider-reported tokens at published prices; not provider-reported cost"},
        "protocol": record.get("protocol_compliance"),
    }
