"""Local artifacts with explicit secret redaction and separate screenshot files."""
import base64
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
        self.secrets = tuple(s for s in secrets if s)
        self.events = 0

    def clean(self, value):
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        if isinstance(value, dict):
            return {str(k): "[REDACTED]" if re.search(r"api_key|authorization|access_token|secret", str(k), re.I)
                    else self.clean(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [self.clean(v) for v in value]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return value
        return value

    def write(self, name: str, value):
        (self.path / name).write_text(json.dumps(self.clean(value), indent=2) + "\n")

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
