"""
AI Client - PlanejaENEM 5.0.

Client centralizado para chamadas à API de IA generativa (OpenRouter).
Fornece chat simples, chat estruturado, retry controlado e rastreamento de uso.

REGRA DE OURO: Este client APENAS envia prompts e recebe respostas.
Nunca executa SQL, acessa o banco, modifica scores ou decide planejamento.
"""

import json
import logging
import random
import time

import httpx

from app.ai.config import AIConfig
from app.ai.cost_estimator import estimate_cost
from app.ai.exceptions import (
    AIDisabledError,
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
    AITimeoutError,
    AIRateLimitError,
)
from app.ai.schemas import (
    ChatRequest,
    ChatResponse,
    StructuredChatResponse,
    UsageInfo,
)
from app.ai.usage import UsageTracker

logger = logging.getLogger(__name__)

# Status codes que justificam retry (exceto 429, que tem lógica própria)
_RETRYABLE_STATUS_CODES = {500, 502, 503}


class AIClient:
    """
    Client centralizado para o AI Gateway.

    Usa httpx.Client (síncrono) para compatibilidade com Flask.
    Uma instância por aplicação (singleton via create_app).
    """

    def __init__(
        self,
        config: AIConfig,
        tracker: UsageTracker,
        rate_limiter=None,
    ) -> None:
        self._config = config
        self._tracker = tracker
        self._rate_limiter = rate_limiter
        self._http: httpx.Client | None = None

        if self._config.enabled:
            self._http = httpx.Client(
                timeout=httpx.Timeout(self._config.timeout, connect=10.0),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30,
                ),
            )

    @property
    def enabled(self) -> bool:
        """Indica se o client está habilitado."""
        return self._config.enabled

    def _ensure_ready(self) -> None:
        """Verifica se o client está pronto para uso."""
        if not self._config.enabled:
            raise AIDisabledError()
        if not self._config.api_key:
            raise AIConfigurationError(
                "OPENROUTER_API_KEY não configurada. "
                "Defina a variável de ambiente OPENROUTER_API_KEY."
            )
        if not self._config.model:
            raise AIConfigurationError(
                "OPENROUTER_MODEL não configurado. "
                "Defina a variável de ambiente OPENROUTER_MODEL."
            )
        if self._http is None:
            raise AIConfigurationError("Cliente HTTP não inicializado.")

    def _build_headers(self) -> dict:
        """Constrói headers para a requisição."""
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://planejaenem.com.br",
            "X-Title": "PlanejaENEM",
        }

    def _should_retry(self, attempt: int, exc: Exception) -> bool:
        """Determina se deve tentar novamente."""
        if attempt >= self._config.max_retries:
            return False
        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, AIProviderError):
            return exc.status_code in _RETRYABLE_STATUS_CODES
        if isinstance(exc, AIRateLimitError):
            return True
        return False

    def _calculate_delay(self, attempt: int) -> float:
        """Calcula delay exponencial com jitter para retry."""
        base_delay = 0.5
        max_delay = 30.0
        delay = min(base_delay * (2 ** attempt), max_delay)
        jitter = random.uniform(0, delay * 0.3)
        return delay + jitter

    def _make_request(self, payload: dict, feature: str = "default") -> dict:
        """
        Executa a requisição HTTP com retry.

        Args:
            payload: Body da requisição.
            feature: Feature que fez a chamada (para tracking).

        Returns:
            Response JSON do provider.

        Raises:
            AITimeoutError: Se timeout após todas as tentativas.
            AIRateLimitError: Se rate limit após todas as tentativas.
            AIProviderError: Se erro do provider após todas as tentativas.
            AIValidationError: Se resposta não é JSON válido.
        """
        self._ensure_ready()
        assert self._http is not None
        assert self._config.model is not None

        headers = self._build_headers()
        url = f"{self._config.base_url}/chat/completions"

        last_exc: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                start_time = time.monotonic()
                response = self._http.post(url, json=payload, headers=headers)
                latency_ms = (time.monotonic() - start_time) * 1000

                if response.status_code == 429:
                    retry_after = None
                    try:
                        error_body = response.json()
                        retry_after = error_body.get("error", {}).get("metadata", {}).get("retry_after")
                    except (json.JSONDecodeError, ValueError):
                        pass

                    exc = AIRateLimitError(
                        message="Rate limit atingido no OpenRouter",
                        retry_after=retry_after,
                    )

                    if not self._should_retry(attempt + 1, exc):
                        self._tracker.record(
                            feature=feature,
                            model=self._config.model,
                            input_tokens=0,
                            output_tokens=0,
                            total_tokens=0,
                            latency_ms=latency_ms,
                            status="rate_limit",
                        )
                        raise exc
                    last_exc = exc
                    delay = retry_after or self._calculate_delay(attempt)
                    logger.warning(
                        "AI rate limit (tentativa %d/%d), retry em %.1fs",
                        attempt + 1,
                        self._config.max_retries + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                if response.status_code not in {200}:
                    provider_msg = ""
                    try:
                        error_body = response.json()
                        provider_msg = str(error_body.get("error", {}).get("message", ""))
                    except (json.JSONDecodeError, ValueError):
                        pass

                    exc = AIProviderError(
                        message=f"Provider retornou status {response.status_code}",
                        status_code=response.status_code,
                        provider_message=provider_msg,
                    )

                    if not self._should_retry(attempt + 1, exc):
                        self._tracker.record(
                            feature=feature,
                            model=self._config.model,
                            input_tokens=0,
                            output_tokens=0,
                            total_tokens=0,
                            latency_ms=latency_ms,
                            status="error",
                        )
                        raise exc
                    last_exc = exc
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        "AI provider error %d (tentativa %d/%d), retry em %.1fs",
                        response.status_code,
                        attempt + 1,
                        self._config.max_retries + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                try:
                    data = response.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    self._tracker.record(
                        feature=feature,
                        model=self._config.model,
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        latency_ms=latency_ms,
                        status="error",
                    )
                    raise AIValidationError(
                        "Resposta do provider não é JSON válido"
                    ) from exc

                return data

            except httpx.TimeoutException as exc:
                latency_ms = (time.monotonic() - start_time) * 1000
                if not self._should_retry(attempt + 1, exc):
                    self._tracker.record(
                        feature=feature,
                        model=self._config.model,
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        latency_ms=latency_ms,
                        status="timeout",
                    )
                    timeout_exc = AITimeoutError(
                        f"Timeout após {self._config.timeout}s"
                    )
                    timeout_exc.timeout_seconds = self._config.timeout
                    raise timeout_exc from exc
                last_exc = exc
                delay = self._calculate_delay(attempt)
                logger.warning(
                    "AI timeout (tentativa %d/%d), retry em %.1fs",
                    attempt + 1,
                    self._config.max_retries + 1,
                    delay,
                )
                time.sleep(delay)

            except (httpx.HTTPError, httpx.TransportError) as exc:
                latency_ms = 0
                self._tracker.record(
                    feature=feature,
                    model=self._config.model,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    latency_ms=latency_ms,
                    status="error",
                )
                raise AIProviderError(
                    message=f"Erro HTTP: {exc}"
                ) from exc

        raise AIProviderError(
            "Todas as tentativas falharam",
            status_code=getattr(last_exc, "status_code", None),
        )

    def chat(self, request: ChatRequest, feature: str = "default") -> ChatResponse:
        """
        Executa uma chamada de chat simples.

        Args:
            request: Request com mensagens e parâmetros.
            feature: Feature que fez a chamada (para tracking).

        Returns:
            ChatResponse com a resposta do modelo.
        """
        self._ensure_ready()
        assert self._config.model is not None

        payload = request.to_dict()
        if "model" not in payload:
            payload["model"] = request.model or self._config.model

        start_time = time.monotonic()
        data = self._make_request(payload, feature=feature)
        latency_ms = (time.monotonic() - start_time) * 1000

        content = ""
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        model = data.get("model", self._config.model)
        usage = UsageInfo.from_dict(data.get("usage"))
        finish_reason = choices[0].get("finish_reason", "stop") if choices else "stop"

        # Calcula custo estimado
        cost = estimate_cost(
            usage.prompt_tokens,
            usage.completion_tokens,
            self._config,
        )

        response = ChatResponse(
            content=content,
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )

        self._tracker.record(
            feature=feature,
            model=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            latency_ms=latency_ms,
            status="success",
            estimated_cost=cost,
        )

        return response

    def chat_structured(
        self,
        request: ChatRequest,
        expected_keys: list[str] | None = None,
        feature: str = "default",
    ) -> StructuredChatResponse:
        """
        Executa uma chamada de chat com resposta estruturada (JSON).

        Valida que a resposta é JSON válido e contém as chaves esperadas.

        Args:
            request: Request com mensagens e parâmetros.
            expected_keys: Lista de chaves obrigatórias no JSON de resposta.
            feature: Feature que fez a chamada (para tracking).

        Returns:
            StructuredChatResponse com dados parseados.

        Raises:
            AIValidationError: Se a resposta não é JSON válido.
            AIValidationError: Se o JSON não contém as chaves esperadas.
        """
        if request.response_format is None:
            request.response_format = {"type": "json_object"}

        chat_response = self.chat(request, feature=feature)

        try:
            parsed = json.loads(chat_response.content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AIValidationError(
                "Resposta não é JSON válido"
            ) from exc

        if not isinstance(parsed, dict):
            raise AIValidationError(
                "Resposta JSON não é um objeto"
            )

        if expected_keys:
            missing = [k for k in expected_keys if k not in parsed]
            if missing:
                exc = AIValidationError(
                    f"Campos obrigatórios ausentes: {', '.join(missing)}"
                )
                exc.missing_fields = missing
                raise exc

        return StructuredChatResponse(
            data=parsed,
            raw_content=chat_response.content,
            model=chat_response.model,
            usage=chat_response.usage,
            latency_ms=chat_response.latency_ms,
        )

    def close(self) -> None:
        """Fecha a conexão HTTP e libera recursos."""
        if self._http is not None:
            self._http.close()
            self._http = None

    def __enter__(self) -> "AIClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __repr__(self) -> str:
        """Repr seguro: nunca expõe api_key."""
        return (
            f"AIClient(enabled={self._config.enabled!r}, "
            f"model={self._config.model!r})"
        )
