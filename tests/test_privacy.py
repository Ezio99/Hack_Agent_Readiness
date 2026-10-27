import json
from pathlib import Path
from urllib.parse import quote, quote_plus
import pytest
from agent_readiness.recorder import Recorder


@pytest.mark.parametrize("payload,secret", [
    ("Authorization: Bearer hidden-header-value", "hidden-header-value"),
    ("Authorization: Token hidden-token-scheme", "hidden-token-scheme"),
    ("proxy-authorization=Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
    ('{"Authorization": "Bearer json-header-value"}', "json-header-value"),
    (repr({"X-API-Key": "unknown-api-key-value"}), "unknown-api-key-value"),
    (json.dumps(json.dumps({"Authorization": "Bearer escaped-header-value"})), "escaped-header-value"),
    ("POST https://host/v1?api_key=query-key-value&public=keep", "query-key-value"),
    ("https://host/v1?access_token=query-token-value", "query-token-value"),
    ("https://username:embedded-password@host/v1", "embedded-password"),
    ("Failure with Bearer standalone-token-value", "standalone-token-value"),
])
def test_unknown_credentials_in_text_errors_are_redacted(tmp_path, payload, secret):
    recorder = Recorder(tmp_path)
    recorder.event("error", message=payload)
    recorder.write("run.json", {"errors": [payload], "endpoint": payload})
    for file in recorder.path.iterdir():
        assert secret not in file.read_text()
        assert "[REDACTED]" in file.read_text()


def test_structured_headers_and_known_secret_encodings_preserve_observations(tmp_path):
    secret = 'fixture/key+with space"and-newline\nend'
    recorder = Recorder(tmp_path, (secret,))
    observation = "City Tote costs $24.00; detail navigation remains visible."
    payload = {"headers": {"AUTHORIZATION": "unregistered-value-one", "X_Api_Key": "unregistered-value-two"},
        "header_pairs": [("X-API-Key", "unregistered-value-three")],
        "paths": [Path("/tmp") / secret], "text": [secret, quote(secret, safe=""), quote_plus(secret), json.dumps(secret)[1:-1]],
        "observation": observation, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    recorder.write("history.json", payload)
    recorder.event("model_error", error=RuntimeError(secret))
    for file in recorder.path.iterdir():
        text = file.read_text()
        for forbidden in [secret, quote(secret, safe=""), quote_plus(secret), json.dumps(secret)[1:-1],
                          "unregistered-value-one", "unregistered-value-two", "unregistered-value-three"]:
            assert forbidden not in text
    saved = json.loads((recorder.path / "history.json").read_text())
    assert saved["observation"] == observation
    assert saved["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
    assert saved["headers"] == {"AUTHORIZATION": "[REDACTED]", "X_Api_Key": "[REDACTED]"}
