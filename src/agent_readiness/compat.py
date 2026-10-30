"""Opt-in Muse compatibility parser (versioned): one complete JSON object preceded by single-line prose.

Why it exists: Muse Spark 1.3 was observed returning ``<one prose sentence><JSON object>`` for full-schema agent
steps even with ``strict`` structured output. The default contract (strict JSON from the first character) is
unchanged; this parser only runs when a profile names it, and it never invents, repairs or edits content: the
normalized text is a byte-identical slice of the original that must validate against the unchanged output model.

Accepted (all must hold):
  * the original is not already strict JSON (otherwise recovery is not needed);
  * a non-empty prefix of at most ``MAX_PREFIX_CHARS`` characters, one line, with no ``{``, ``[`` or code fence;
  * the first ``{`` starts a JSON object that decodes completely (no duplicate keys, no NaN/Infinity);
  * nothing but whitespace follows the object (no second object, no trailing prose);
  * the object validates against the output model supplied by the caller.
"""
import hashlib
import json

PARSER_ID = "muse-prose-prefix-json-v1"
SUPPORTED_PARSERS = (PARSER_ID,)
MAX_PREFIX_CHARS = 500
MAX_CONTENT_CHARS = 20_000


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _reject_constants(name):
    raise ValueError(f"non-standard JSON constant {name}")


def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate keys")
    return dict(pairs)


def recover(content, output_format) -> dict:
    """Classify ``content`` and, if it matches the accepted pattern, return the normalized text.

    Returns a JSON-serialisable dict. ``status`` is ``not_needed``, ``recovered`` or ``rejected``; a recovery is
    only reported when the normalized text validates (``validated`` true). Never raises on model content."""
    result = {"parser": PARSER_ID, "status": "rejected", "reason": None, "raw_protocol_compliant": False,
              "validated": False, "prefix_chars": None, "json_offset": None, "json_chars": None,
              "original_sha256": None, "normalized": None, "normalized_sha256": None,
              "validation_errors": None, "actions": None}

    def reject(reason):
        result["reason"] = reason
        return result

    if not isinstance(content, str) or not content.strip():
        return reject("empty_or_non_string")
    result["original_sha256"] = sha256(content)
    if len(content) > MAX_CONTENT_CHARS:
        return reject("content_too_long")
    try:
        json.loads(content)
        result.update(status="not_needed", reason="already_strict_json", raw_protocol_compliant=True)
        return result
    except ValueError:
        pass
    start = content.find("{")
    if start < 0:
        return reject("no_json_object")
    prefix = content[:start]
    if not prefix.strip():
        return reject("no_prose_prefix")  # leading whitespace then invalid JSON: not this pattern
    result["prefix_chars"], result["json_offset"] = len(prefix), start
    if len(prefix) > MAX_PREFIX_CHARS:
        return reject("prefix_too_long")
    if "\n" in prefix or "\r" in prefix:
        return reject("multi_line_prefix")
    if "[" in prefix or "```" in prefix:
        return reject("prefix_contains_json_like_or_fence")
    decoder = json.JSONDecoder(object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constants)
    try:
        value, end = decoder.raw_decode(content, start)
    except ValueError as exc:
        return reject("incomplete_or_invalid_json" if "duplicate" not in str(exc) and "constant" not in str(exc)
                      else "duplicate_keys_or_nonstandard_constant")
    if not isinstance(value, dict):
        return reject("not_an_object")
    trailing = content[end:]
    result["json_chars"] = end - start
    if trailing.strip():
        return reject("multiple_objects_or_trailing_material" if "{" in trailing else "trailing_material")
    normalized = content[start:end]
    result["normalized"], result["normalized_sha256"] = normalized, sha256(normalized)
    try:
        parsed = output_format.model_validate_json(normalized)
    except Exception as exc:  # pydantic.ValidationError; input values are not recorded
        errors = exc.errors(include_input=False, include_url=False)[:20] if hasattr(exc, "errors") else []
        result["validation_errors"] = [{"loc": [str(p) for p in e.get("loc", ())], "type": e.get("type")} for e in errors]
        result["normalized"] = None  # not offered for use
        return reject("schema_invalid")
    result.update(status="recovered", reason="prose_prefix_single_json_object", validated=True)
    actions = getattr(parsed, "action", None)
    if actions is not None:
        if hasattr(actions, "model_dump"):          # a SINGLE action object (e.g. the investigator's tool call), not Browser Use's list: iterating a model would yield (name, value) tuples
            actions = [actions]
        result["actions"] = [sorted(a.model_dump(exclude_none=True)) for a in actions]
    return result
