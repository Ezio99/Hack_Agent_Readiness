"""No model calls or agent self-assessment in outcome grading."""
from pydantic import ValidationError
from .contracts import Answer, Evaluation
from .inventory import PRODUCTS
from .tasks import PrivateTask


def evaluate(raw: object, task: PrivateTask) -> Evaluation:
    try:
        answer = Answer.model_validate(raw)
    except ValidationError:
        return Evaluation(passed=False, reasons=["Malformed answer: expected product_id, integer price_cents, boolean available"])
    product = next((p for p in PRODUCTS if p.product_id == answer.product_id), None)
    reasons = []
    if product is None:
        reasons.append("Unknown product ID")
    else:
        if answer.product_id != task.expected_id:
            reasons.append("Product ID does not match the task target")
        if not task.matches(product):
            reasons.append("Product does not satisfy task constraints")
        if answer.price_cents != product.price_cents:
            reasons.append("Price differs from inventory truth")
        if answer.available != product.available:
            reasons.append("Availability differs from inventory truth")
    return Evaluation(passed=not reasons, reasons=reasons or ["All required fields match inventory truth and task constraints"])
