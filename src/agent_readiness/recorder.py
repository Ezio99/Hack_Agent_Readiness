"""Local artifacts with explicit secret redaction and separate screenshot files."""
import base64
from collections.abc import Mapping
import math
from urllib.parse import quote, quote_plus
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Recorder:
    def __init__(self, root: Path, secrets: tuple[str, ...] = ()):
        self.path = root / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:12]}"
        self.path.mkdir(parents=True)
        self.secrets = set()
        for secret in secrets:
            self.add_secret(secret)
        self.events = 0

    @staticmethod
    def sensitive_key(key):
        normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
        return normalized == "token" or any(part in normalized for part in (
            "apikey", "authorization", "accesstoken", "refreshtoken", "clientsecret",
            "password", "secret", "cookie"))

    def add_secret(self, secret):
        if hasattr(secret, "get_secret_value"):
            secret = secret.get_secret_value()
        if isinstance(secret, str) and secret:
            self.secrets.update((secret, quote(secret, safe=""), quote_plus(secret),
                                 json.dumps(secret)[1:-1]))

    def clean(self, value):
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        if isinstance(value, Mapping):
            return {self.clean(str(k)): "[REDACTED]" if self.sensitive_key(k)
                    else self.clean(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            if len(value) == 2 and isinstance(value[0], str) and self.sensitive_key(value[0]):
                return [self.clean(value[0]), "[REDACTED]"]
            return [self.clean(v) for v in value]
        if isinstance(value, (Path, BaseException)):
            return self.clean(str(value))
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, str):
            for secret in sorted(self.secrets, key=len, reverse=True):
                value = value.replace(secret, "[REDACTED]")
            # SDK/HTTP errors can embed headers, URL credentials, or query keys.
            # Match recognizable credential fields even if their value is not the
            # adapter's configured key (e.g. a server-returned authorization header).
            value = re.sub(
                r"(?i)(\b(?:x[-_]api[-_]key|api[-_]?key|access[-_]token|refresh[-_]token|client[-_]secret|password|token|(?:proxy[-_])?authorization)\b[\\\"']*\s*[:=]\s*[\\\"']*)(?:(?:Bearer|Basic|Token|ApiKey)\s+)?[^\s\\\"',;&<>]+",
                r"\1[REDACTED]", value)
            value = re.sub(r"(?i)\bBearer\s+[^\s\\\"',;&<>]+", "Bearer [REDACTED]", value)
            value = re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", value)
            return value
        return value

    def write(self, name: str, value):
        (self.path / name).write_text(json.dumps(self.clean(value), indent=2) + "\n")

    def text(self, name: str, value: str):
        (self.path / name).write_text(self.clean(value))

    def image(self, label: str, data: str) -> str:
        name = f"{label}.png"
        (self.path / name).write_bytes(base64.b64decode(data))
        return name

    def messages(self, value):
        """Preserve text and image inputs without bloating JSONL with base64."""
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        if isinstance(value, list):
            return [self.messages(v) for v in value]
        if isinstance(value, dict):
            return {k: self.messages(v) for k, v in value.items()}
        if isinstance(value, str) and value.startswith("data:image/") and ";base64," in value:
            return self.image(f"model-input-{uuid.uuid4().hex[:12]}", value.split(",", 1)[1])
        return value

    def event(self, kind: str, **data):
        self.events += 1
        event = self.clean({"sequence": self.events, "timestamp": utcnow(), "kind": kind, **data})
        with (self.path / "trace.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")
