"""
Configuração do AI Gateway - PlanejaENEM 5.0.

Centraliza todas as variáveis de ambiente relacionadas à IA.
A configuração é carregada uma vez e imutável após a criação.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AIConfig:
    """
    Configuração do AI Gateway.

    Todos os valores são lidos de variáveis de ambiente com defaults seguros.
    A aplicação funciona normalmente com enabled=False (IA desligada).
    """

    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = ""
    timeout: float = 30.0
    max_retries: int = 2
    max_tokens: int = 2048

    def __repr__(self) -> str:
        """Repr seguro: nunca expõe api_key."""
        return (
            f"AIConfig(enabled={self.enabled!r}, model={self.model!r}, "
            f"base_url={self.base_url!r}, timeout={self.timeout!r}, "
            f"max_retries={self.max_retries!r}, max_tokens={self.max_tokens!r}, "
            f"api_key={'***' if self.api_key else ''})"
        )

    def __str__(self) -> str:
        """Str seguro: nunca expõe api_key."""
        return self.__repr__()


def load_ai_config() -> AIConfig:
    """Carrega configuração do AI Gateway a partir de variáveis de ambiente."""

    def _parse_bool(value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _parse_float(value: str | None, default: float = 30.0) -> float:
        if value is None:
            return default
        try:
            result = float(value)
            if result <= 0:
                return default
            return result
        except (ValueError, TypeError):
            return default

    def _parse_int(value: str | None, default: int = 2) -> int:
        if value is None:
            return default
        try:
            result = int(value)
            if result < 0:
                return default
            return result
        except (ValueError, TypeError):
            return default

    return AIConfig(
        enabled=_parse_bool(os.environ.get("AI_ENABLED"), default=False),
        api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
        base_url=os.environ.get("AI_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        model=os.environ.get("OPENROUTER_MODEL", "").strip(),
        timeout=_parse_float(os.environ.get("AI_TIMEOUT"), default=30.0),
        max_retries=_parse_int(os.environ.get("AI_MAX_RETRIES"), default=2),
        max_tokens=_parse_int(os.environ.get("AI_MAX_TOKENS"), default=2048),
    )
