"""Muse compatibility parser: the captured Stage D pattern and adversarial responses (offline, no network)."""
import json
import pytest
from agent_readiness.compat import MAX_PREFIX_CHARS, PARSER_ID, recover, sha256
from agent_readiness.probe import build_agent_output_schema

# Sanitized content captured live from the full-schema replay (request 3d18e930-9b39-45ba-9e1a-219391b8948e).
PREFIX = "Visually matched — the Fern Home item at $29 is in view, so I'll open it to confirm the details."
OBJECT = ('{"action": [{"click": {"index": 174}}], "current_plan_item": 0, '
          '"evaluation_previous_goal": "Navigated to storefront, identified candidate Linen Cushion Fern Home $29.00", '
          '"memory": "Candidate is Linen Cushion Fern Home $29.00, need to open detail for ID and availability", '
          '"next_goal": "Open Linen Cushion product page to get ID and availability", "plan_update": null, '
          '"thinking": "Browser shows Linen Cushion Fern Home $29 satisfies filter (Fern, Home, <=29). Need product '
          'details page for product_id and availability. Click link 174."}')
CAPTURED = PREFIX + OBJECT


@pytest.fixture(scope="module")
def output_model():
    return build_agent_output_schema()[1]


def test_captured_stage_d_pattern_is_recovered_exactly_and_the_click_validates(output_model):
    result = recover(CAPTURED, output_model)
    assert result["status"] == "recovered" and result["validated"] is True and result["raw_protocol_compliant"] is False
    assert result["normalized"] == OBJECT == CAPTURED[result["json_offset"]:result["json_offset"] + result["json_chars"]]
    assert result["prefix_chars"] == len(PREFIX) == result["json_offset"] and result["actions"] == [["click"]]
    assert result["normalized_sha256"] == sha256(OBJECT) and result["original_sha256"] == sha256(CAPTURED)
    parsed = output_model.model_validate_json(result["normalized"])  # the unchanged AgentOutput schema
    assert parsed.action[0].model_dump(exclude_none=True) == {"click": {"index": 174}}
    assert parsed.next_goal.startswith("Open Linen Cushion")
    json.dumps(result)  # serialisable for the trace


def test_pure_strict_json_is_not_touched(output_model):
    result = recover(OBJECT, output_model)
    assert result["status"] == "not_needed" and result["raw_protocol_compliant"] is True and result["normalized"] is None


@pytest.mark.parametrize("content,reason", [
    (PREFIX + OBJECT + OBJECT, "multiple_objects_or_trailing_material"),                  # two objects
    (PREFIX + OBJECT + " " + OBJECT, "multiple_objects_or_trailing_material"),
    (PREFIX + OBJECT + " and that is all.", "trailing_material"),                          # trailing prose
    (PREFIX + OBJECT + "```", "trailing_material"),
    (PREFIX + OBJECT[:-1], "incomplete_or_invalid_json"),                                  # truncated JSON
    (PREFIX + OBJECT[:80], "incomplete_or_invalid_json"),
    (PREFIX, "no_json_object"),                                                           # prose only
    ("", "empty_or_non_string"), ("   \n ", "empty_or_non_string"), (None, "empty_or_non_string"),
    ("  " + OBJECT[:-1], "no_prose_prefix"),                                              # not this pattern
    ("Here it is {note}. " + OBJECT, "incomplete_or_invalid_json"),                        # brace in the prose
    ("See [1] " + OBJECT, "prefix_contains_json_like_or_fence"),
    ("```json\n" + OBJECT + "\n```", "multi_line_prefix"),                                # fenced / multi-line
    ("Here you go:\n" + OBJECT, "multi_line_prefix"),
    ("```json " + OBJECT, "prefix_contains_json_like_or_fence"),
    ("x" * (MAX_PREFIX_CHARS + 1) + OBJECT, "prefix_too_long"),
    (PREFIX + '{"a": 1, "a": 2}', "duplicate_keys_or_nonstandard_constant"),               # duplicate keys
    (PREFIX + '{"a": NaN}', "duplicate_keys_or_nonstandard_constant"),
    (PREFIX + "[1, 2]", "no_json_object"),                                                # array, not object
    ("y" * 30_000, "content_too_long"),
])
def test_ambiguous_incomplete_or_unsupported_responses_are_rejected(output_model, content, reason):
    result = recover(content, output_model)
    assert result["status"] == "rejected" and result["reason"] == reason, result
    assert result["normalized"] is None and result["validated"] is False


def mutated(change):
    value = json.loads(OBJECT)
    change(value)
    return PREFIX + json.dumps(value)


@pytest.mark.parametrize("change", [
    lambda v: v.pop("action"),                                     # missing required field (fields with schema defaults behave as in the strict path)
    lambda v: v.__setitem__("action", "click 174"),                # wrong type
    lambda v: v.__setitem__("action", [{"teleport": {"index": 1}}]),  # unknown action
    lambda v: v.__setitem__("action", [{"click": {"index": "x"}}]),  # invalid action argument
    lambda v: v.__setitem__("extra_field", 1),                     # extra property (schema forbids)
    lambda v: v.__setitem__("action", [{"click": {"index": 1}, "navigate": {"url": "http://x", "new_tab": False}}]),  # two actions in one item
])
def test_prose_plus_schema_invalid_object_is_rejected_without_repair(output_model, change):
    result = recover(mutated(change), output_model)
    assert result["status"] == "rejected" and result["reason"] == "schema_invalid"
    assert result["normalized"] is None and result["validation_errors"]  # locations/types only, no input values


def test_recovery_never_alters_or_invents_fields(output_model):
    value = json.loads(OBJECT)
    value["action"] = [{"click": {"index": 7}}]
    text = PREFIX + json.dumps(value)
    result = recover(text, output_model)
    parsed = output_model.model_validate_json(result["normalized"])
    assert parsed.action[0].model_dump(exclude_none=True) == {"click": {"index": 7}}  # exactly what was sent
    assert result["normalized"] == json.dumps(value)  # byte-identical slice, not re-serialised


def test_unicode_quotes_and_braces_inside_json_strings_are_handled(output_model):
    value = json.loads(OBJECT)
    value["memory"] = 'has "quotes", a } brace, a { brace and ünïcode — ✓'
    result = recover("Prose with unicode ✓ — ok. " + json.dumps(value, ensure_ascii=False), output_model)
    assert result["status"] == "recovered" and json.loads(result["normalized"])["memory"] == value["memory"]


def test_recover_never_raises_on_odd_model_content(output_model):
    for content in ["\x00", "{" * 5000, "}" * 5000, "a" * 100 + "{" + "\ud800", 5, [], {}, b"bytes"]:
        assert recover(content, output_model)["status"] in {"rejected", "not_needed"}
