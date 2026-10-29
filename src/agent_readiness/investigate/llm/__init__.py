"""Provider interfaces for the investigator (plan D8). `ScriptedClient` and `RecordedClient` make no network calls; `MetaClient` only talks to the network through the durable spend gate."""
from .client import LLMClient, LLMRequest, LLMResponse, StructuredOutputError, complete_structured, request_sha256
from .recorded import RecordedClient, RecordingClient
from .scripted import ScriptedClient

__all__ = ["LLMClient", "LLMRequest", "LLMResponse", "StructuredOutputError", "complete_structured", "request_sha256", "RecordedClient", "RecordingClient", "ScriptedClient"]
