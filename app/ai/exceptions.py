"""
Exceções do AI Gateway - PlanejaENEM 5.0.

Hierarquia de exceções para erros específicos do gateway de IA.
Permite que chamadores tratem cada tipo de erro de forma granular.
"""


class AIError(Exception):
    """Exceção base do AI Gateway."""

    def __init__(self, message: str = "Erro desconhecido no AI Gateway") -> None:
        super().__init__(message)
        self.message = message


class AIDisabledError(AIError):
    """IA está desligada (AI_ENABLED=false ou ausente)."""

    def __init__(self, message: str = "IA está desligada (AI_ENABLED=false)") -> None:
        super().__init__(message)


class AIConfigurationError(AIError):
    """Configuração inválida ou obrigatória ausente (ex: API key)."""

    def __init__(self, message: str = "Configuração do AI Gateway inválida") -> None:
        super().__init__(message)


class AITimeoutError(AIError):
    """Timeout na chamada ao provider de IA."""

    def __init__(self, message: str = "Timeout na chamada ao provider de IA") -> None:
        super().__init__(message)
        self.timeout_seconds: float | None = None


class AIRateLimitError(AIError):
    """Rate limit atingido no provider de IA (HTTP 429)."""

    def __init__(
        self,
        message: str = "Rate limit atingido no provider de IA",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AIProviderError(AIError):
    """Erro retornado pelo provider de IA (5xx, etc)."""

    def __init__(
        self,
        message: str = "Erro do provider de IA",
        status_code: int | None = None,
        provider_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_message = provider_message


class AIValidationError(AIError):
    """Resposta do provider não é JSON válido, está malformada ou não bate com schema."""

    def __init__(self, message: str = "Resposta inválida do provider") -> None:
        super().__init__(message)
        self.missing_fields: list[str] = []
        self.extra_fields: list[str] = []
