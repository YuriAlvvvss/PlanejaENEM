"""
Schemas do AI Gateway - PlanejaENEM 5.0.

Dataclasses para requests e responses do gateway de IA.
Todos são serializáveis e validáveis sem dependências externas.
"""

from dataclasses import dataclass


@dataclass
class Message:
    """Mensagem no formato OpenAI Chat Completions."""

    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatRequest:
    """Request para Chat Completions API."""

    messages: list[Message]
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    response_format: dict | None = None

    def to_dict(self) -> dict:
        payload: dict = {
            "messages": [m.to_dict() for m in self.messages],
        }
        if self.model is not None:
            payload["model"] = self.model
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.response_format is not None:
            payload["response_format"] = self.response_format
        return payload


@dataclass
class UsageInfo:
    """Informações de uso de tokens retornadas pelo provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict | None) -> "UsageInfo":
        if not data:
            return cls()
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )


@dataclass
class ChatResponse:
    """Resposta simples do Chat Completions API."""

    content: str
    model: str
    usage: UsageInfo
    latency_ms: float
    finish_reason: str = "stop"


@dataclass
class StructuredChatResponse:
    """Resposta estruturada (JSON parsed) do Chat Completions API."""

    data: dict
    raw_content: str
    model: str
    usage: UsageInfo
    latency_ms: float
