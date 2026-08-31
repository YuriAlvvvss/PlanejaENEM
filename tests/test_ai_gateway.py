"""
Testes do AI Gateway - PlanejaENEM 5.0.

Suite completa de testes para o módulo de IA generativa.
Todos os testes usam mocks — nenhuma chamada real ao OpenRouter.
"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.ai import (
    AIClient,
    AIConfig,
    AIDisabledError,
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIRateLimitError,
    AIValidationError,
    AITimeoutError,
    ChatRequest,
    ChatResponse,
    Message,
    StructuredChatResponse,
    UsageInfo,
    UsageTracker,
    load_ai_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ai_config_enabled():
    """Configuração com IA habilitada."""
    return AIConfig(
        enabled=True,
        api_key="test-api-key-12345",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
        timeout=5.0,
        max_retries=2,
        max_tokens=1024,
    )


@pytest.fixture
def ai_config_disabled():
    """Configuração com IA desabilitada."""
    return AIConfig(enabled=False)


@pytest.fixture
def tracker():
    """UsageTracker limpo."""
    return UsageTracker()


@pytest.fixture
def client_enabled(ai_config_enabled, tracker):
    """AIClient habilitado para testes."""
    return AIClient(ai_config_enabled, tracker)


@pytest.fixture
def client_disabled(ai_config_disabled, tracker):
    """AIClient desabilitado para testes."""
    return AIClient(ai_config_disabled, tracker)


def _simple_request():
    """Cria um ChatRequest simples para testes."""
    return ChatRequest(
        messages=[Message(role="user", content="O que é 2+2?")],
        temperature=0.5,
    )


def _openrouter_response(content="4", model="openai/gpt-4o-mini"):
    """Cria uma resposta simulada do OpenRouter."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


# ---------------------------------------------------------------------------
# Testes: AIConfig
# ---------------------------------------------------------------------------

class TestAIConfig:
    """Testes para a configuração do AI Gateway."""

    def test_default_config(self):
        """Configuração padrão deve estar desabilitada."""
        config = AIConfig()
        assert config.enabled is False
        assert config.api_key == ""
        assert config.model == ""

    def test_repr_nao_expoe_api_key(self):
        """repr() nunca deve expor a API key."""
        config = AIConfig(enabled=True, api_key="sk-super-secret-12345")
        assert "sk-super-secret" not in repr(config)
        assert "***" in repr(config)

    def test_str_nao_expoe_api_key(self):
        """str() nunca deve expor a API key."""
        config = AIConfig(enabled=True, api_key="sk-super-secret-12345")
        assert "sk-super-secret" not in str(config)

    def test_config_e_frozen(self):
        """AIConfig deve ser imutável (frozen)."""
        config = AIConfig()
        with pytest.raises(AttributeError):
            config.enabled = True


class TestLoadAIConfig:
    """Testes para load_ai_config()."""

    def test_default_values(self):
        """Valores padrão quando variáveis não estão definidas."""
        import os
        with patch.dict(os.environ, {}, clear=True):
            # Remove vars se existirem
            for key in ["AI_ENABLED", "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
                        "AI_BASE_URL", "AI_TIMEOUT", "AI_MAX_RETRIES", "AI_MAX_TOKENS"]:
                os.environ.pop(key, None)
            config = load_ai_config()
            assert config.enabled is False
            assert config.api_key == ""
            assert config.model == ""

    def test_enabled_true(self):
        """AI_ENABLED=true deve habilitar."""
        import os
        with patch.dict(os.environ, {"AI_ENABLED": "true"}, clear=False):
            os.environ["AI_ENABLED"] = "true"
            config = load_ai_config()
            assert config.enabled is True

    def test_api_key_from_env(self):
        """OPENROUTER_API_KEY deve ser lida."""
        import os
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            config = load_ai_config()
            assert config.api_key == "test-key"

    def test_model_from_env(self):
        """OPENROUTER_MODEL deve ser lido."""
        import os
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "anthropic/claude-3"}, clear=False):
            config = load_ai_config()
            assert config.model == "anthropic/claude-3"

    def test_timeout_parsing(self):
        """AI_TIMEOUT deve ser parseado corretamente."""
        import os
        with patch.dict(os.environ, {"AI_TIMEOUT": "15.5"}, clear=False):
            config = load_ai_config()
            assert config.timeout == 15.5

    def test_timeout_invalid_uses_default(self):
        """Valor inválido para timeout deve usar default."""
        import os
        with patch.dict(os.environ, {"AI_TIMEOUT": "abc"}, clear=False):
            config = load_ai_config()
            assert config.timeout == 30.0


# ---------------------------------------------------------------------------
# Testes: Exceptions
# ---------------------------------------------------------------------------

class TestExceptions:
    """Testes para a hierarquia de exceções."""

    def test_heranca(self):
        """Todas as exceções devem herdar de AIError."""
        assert issubclass(AIDisabledError, AIError)
        assert issubclass(AIConfigurationError, AIError)
        assert issubclass(AITimeoutError, AIError)
        assert issubclass(AIRateLimitError, AIError)
        assert issubclass(AIProviderError, AIError)
        assert issubclass(AIValidationError, AIError)

    def test_ai_error_base_message(self):
        """AIError deve aceitar mensagem customizada."""
        exc = AIError("teste")
        assert str(exc) == "teste"
        assert exc.message == "teste"

    def test_timeout_error_has_timeout_seconds(self):
        """AITimeoutError deve ter timeout_seconds."""
        exc = AITimeoutError("timeout")
        assert exc.timeout_seconds is None

    def test_rate_limit_error_has_retry_after(self):
        """AIRateLimitError deve ter retry_after."""
        exc = AIRateLimitError("rate limit", retry_after=5.0)
        assert exc.retry_after == 5.0

    def test_provider_error_has_status_code(self):
        """AIProviderError deve ter status_code."""
        exc = AIProviderError("erro", status_code=500)
        assert exc.status_code == 500

    def test_validation_error_has_missing_fields(self):
        """AIValidationError deve ter missing_fields."""
        exc = AIValidationError("schema inválido")
        assert exc.missing_fields == []


# ---------------------------------------------------------------------------
# Testes: UsageTracker
# ---------------------------------------------------------------------------

class TestUsageTracker:
    """Testes para o rastreador de uso."""

    def test_record(self):
        """Deve registrar chamadas."""
        tracker = UsageTracker()
        tracker.record(
            feature="explanation",
            model="openai/gpt-4o-mini",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            latency_ms=150.0,
            status="success",
        )
        assert len(tracker.get_records()) == 1

    def test_summary_empty(self):
        """Summary vazio quando não há registros."""
        tracker = UsageTracker()
        summary = tracker.summary()
        assert summary["total_calls"] == 0

    def test_summary_with_records(self):
        """Summary deve agregar corretamente."""
        tracker = UsageTracker()
        tracker.record("f1", "m1", 10, 5, 15, 100.0, "success")
        tracker.record("f2", "m1", 20, 10, 30, 200.0, "error")
        summary = tracker.summary()
        assert summary["total_calls"] == 2
        assert summary["total_input_tokens"] == 30
        assert summary["total_output_tokens"] == 15
        assert summary["total_tokens"] == 45
        assert summary["success_calls"] == 1
        assert summary["error_calls"] == 1

    def test_reset(self):
        """reset() deve limpar registros."""
        tracker = UsageTracker()
        tracker.record("f1", "m1", 10, 5, 15, 100.0, "success")
        tracker.reset()
        assert len(tracker.get_records()) == 0

    def test_record_has_timestamp(self):
        """Cada registro deve ter um timestamp."""
        tracker = UsageTracker()
        tracker.record("f1", "m1", 10, 5, 15, 100.0, "success")
        record = tracker.get_records()[0]
        assert isinstance(record.timestamp, datetime)


# ---------------------------------------------------------------------------
# Testes: Schemas
# ---------------------------------------------------------------------------

class TestSchemas:
    """Testes para os schemas de request/response."""

    def test_message_to_dict(self):
        """Message.to_dict() deve retornar dict correto."""
        msg = Message(role="user", content="teste")
        assert msg.to_dict() == {"role": "user", "content": "teste"}

    def test_chat_request_to_dict(self):
        """ChatRequest.to_dict() deve serializar corretamente."""
        req = ChatRequest(
            messages=[Message(role="user", content="oi")],
            model="test-model",
            temperature=0.3,
        )
        d = req.to_dict()
        assert d["model"] == "test-model"
        assert d["temperature"] == 0.3
        assert len(d["messages"]) == 1

    def test_chat_request_optional_fields(self):
        """Campos opcionais não devem aparecer no dict."""
        req = ChatRequest(messages=[Message(role="user", content="oi")])
        d = req.to_dict()
        assert "model" not in d
        assert "max_tokens" not in d
        assert "response_format" not in d

    def test_usage_info_from_dict(self):
        """UsageInfo.from_dict() deve parsear corretamente."""
        usage = UsageInfo.from_dict({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 5
        assert usage.total_tokens == 15

    def test_usage_info_from_none(self):
        """UsageInfo.from_dict(None) deve retornar defaults."""
        usage = UsageInfo.from_dict(None)
        assert usage.total_tokens == 0


# ---------------------------------------------------------------------------
# Testes: AIClient - Modo desativado
# ---------------------------------------------------------------------------

class TestAIClientDisabled:
    """Testes para quando a IA está desligada."""

    def test_client_disabled_nao_chama_api(self):
        """Client desabilitado não deve criar httpx.Client."""
        client = AIClient(AIConfig(enabled=False), UsageTracker())
        assert client._http is None
        assert client.enabled is False

    def test_chat_raises_aidisabled(self):
        """chat() com client desabilitado deve levantar AIDisabledError."""
        client = AIClient(AIConfig(enabled=False), UsageTracker())
        with pytest.raises(AIDisabledError):
            client.chat(_simple_request())

    def test_chat_structured_raises_aidisabled(self):
        """chat_structured() com client desabilitado deve levantar AIDisabledError."""
        client = AIClient(AIConfig(enabled=False), UsageTracker())
        with pytest.raises(AIDisabledError):
            client.chat_structured(_simple_request())


# ---------------------------------------------------------------------------
# Testes: AIClient - API key ausente
# ---------------------------------------------------------------------------

class TestAIClientNoApiKey:
    """Testes para quando a API key está ausente."""

    def test_chat_raises_aiconfiguration(self):
        """chat() sem API key deve levantar AIConfigurationError."""
        config = AIConfig(enabled=True, api_key="", model="test-model")
        client = AIClient(config, UsageTracker())
        with pytest.raises(AIConfigurationError):
            client.chat(_simple_request())

    def test_chat_structured_raises_aiconfiguration(self):
        """chat_structured() sem API key deve levantar AIConfigurationError."""
        config = AIConfig(enabled=True, api_key="", model="test-model")
        client = AIClient(config, UsageTracker())
        with pytest.raises(AIConfigurationError):
            client.chat_structured(_simple_request())


# ---------------------------------------------------------------------------
# Testes: AIClient - Modelo ausente
# ---------------------------------------------------------------------------

class TestAIClientNoModel:
    """Testes para quando o modelo não está configurado."""

    def test_chat_raises_aiconfiguration(self):
        """chat() sem modelo deve levantar AIConfigurationError."""
        config = AIConfig(enabled=True, api_key="test-key", model="")
        client = AIClient(config, UsageTracker())
        with pytest.raises(AIConfigurationError):
            client.chat(_simple_request())


# ---------------------------------------------------------------------------
# Testes: AIClient - Sucesso
# ---------------------------------------------------------------------------

class TestAIClientSuccess:
    """Testes para chamadas bem-sucedidas."""

    def test_chat_sucesso(self):
        """chat() deve retornar ChatResponse em caso de sucesso."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openrouter_response()

        with patch.object(client._http, "post", return_value=mock_response):
            response = client.chat(_simple_request())

        assert isinstance(response, ChatResponse)
        assert response.content == "4"
        assert response.model == "openai/gpt-4o-mini"
        assert response.usage.total_tokens == 15

    def test_chat_registra_usage(self):
        """chat() deve registrar uso no tracker."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openrouter_response()

        with patch.object(client._http, "post", return_value=mock_response):
            client.chat(_simple_request(), feature="explanation")

        records = tracker.get_records()
        assert len(records) == 1
        assert records[0].feature == "explanation"
        assert records[0].status == "success"

    def test_chat_com_feature(self):
        """chat() deve aceitar parâmetro feature."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openrouter_response()

        with patch.object(client._http, "post", return_value=mock_response):
            client.chat(_simple_request(), feature="summary")

        assert tracker.get_records()[0].feature == "summary"


# ---------------------------------------------------------------------------
# Testes: AIClient - Structured Output
# ---------------------------------------------------------------------------

class TestAIClientStructured:
    """Testes para chat_structured()."""

    def test_structured_sucesso(self):
        """chat_structured() deve retornar StructuredChatResponse."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        json_response = json.dumps({"answer": "4", "confidence": 0.99})
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = _openrouter_response(content=json_response)

        with patch.object(client._http, "post", return_value=mock_http_response):
            response = client.chat_structured(
                _simple_request(),
                expected_keys=["answer", "confidence"],
                feature="structured_test",
            )

        assert isinstance(response, StructuredChatResponse)
        assert response.data["answer"] == "4"
        assert response.data["confidence"] == 0.99

    def test_structured_json_invalido(self):
        """chat_structured() com JSON inválido deve levantar AIValidationError."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = _openrouter_response(content="isto nao e json")

        with patch.object(client._http, "post", return_value=mock_http_response):
            with pytest.raises(AIValidationError):
                client.chat_structured(_simple_request(), feature="test")

    def test_structured_campos_ausentes(self):
        """chat_structured() com campos ausentes deve levantar AIValidationError."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        json_response = json.dumps({"answer": "4"})
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = _openrouter_response(content=json_response)

        with patch.object(client._http, "post", return_value=mock_http_response):
            with pytest.raises(AIValidationError) as exc_info:
                client.chat_structured(
                    _simple_request(),
                    expected_keys=["answer", "confidence"],
                    feature="test",
                )
            assert "confidence" in exc_info.value.missing_fields


# ---------------------------------------------------------------------------
# Testes: AIClient - Timeout
# ---------------------------------------------------------------------------

class TestAIClientTimeout:
    """Testes para timeout."""

    def test_timeout_raises_aitimeout(self):
        """Timeout deve levantar AITimeoutError."""
        import httpx as httpx_module

        config = AIConfig(enabled=True, api_key="test-key", model="test-model",
                         timeout=1.0, max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        with patch.object(client._http, "post", side_effect=httpx_module.TimeoutException("timeout")):
            with pytest.raises(AITimeoutError) as exc_info:
                client.chat(_simple_request())
            assert exc_info.value.timeout_seconds == 1.0

    def test_timeout_registra_no_tracker(self):
        """Timeout deve ser registrado no tracker."""
        import httpx as httpx_module

        config = AIConfig(enabled=True, api_key="test-key", model="test-model",
                         timeout=1.0, max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        with patch.object(client._http, "post", side_effect=httpx_module.TimeoutException("timeout")):
            with pytest.raises(AITimeoutError):
                client.chat(_simple_request())

        records = tracker.get_records()
        assert len(records) == 1
        assert records[0].status == "timeout"


# ---------------------------------------------------------------------------
# Testes: AIClient - Provider Error
# ---------------------------------------------------------------------------

class TestAIClientProviderError:
    """Testes para erros do provider."""

    def test_provider_500_raises_aiprovider(self):
        """HTTP 500 deve levantar AIProviderError."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Internal error"}}

        with patch.object(client._http, "post", return_value=mock_response):
            with pytest.raises(AIProviderError) as exc_info:
                client.chat(_simple_request())
            assert exc_info.value.status_code == 500

    def test_provider_500_registra_no_tracker(self):
        """HTTP 500 deve ser registrado no tracker."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Internal error"}}

        with patch.object(client._http, "post", return_value=mock_response):
            with pytest.raises(AIProviderError):
                client.chat(_simple_request())

        records = tracker.get_records()
        assert len(records) == 1
        assert records[0].status == "error"


# ---------------------------------------------------------------------------
# Testes: AIClient - Rate Limit
# ---------------------------------------------------------------------------

class TestAIClientRateLimit:
    """Testes para rate limit (429)."""

    def test_rate_limit_raises_airatelimit(self):
        """HTTP 429 deve levantar AIRateLimitError."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limited"}}

        with patch.object(client._http, "post", return_value=mock_response):
            with pytest.raises(AIRateLimitError):
                client.chat(_simple_request())

    def test_rate_limit_registra_no_tracker(self):
        """HTTP 429 deve ser registrado no tracker."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limited"}}

        with patch.object(client._http, "post", return_value=mock_response):
            with pytest.raises(AIRateLimitError):
                client.chat(_simple_request())

        records = tracker.get_records()
        assert len(records) == 1
        assert records[0].status == "rate_limit"


# ---------------------------------------------------------------------------
# Testes: AIClient - Retry
# ---------------------------------------------------------------------------

class TestAIClientRetry:
    """Testes para mecanismo de retry."""

    def test_retry_timeout(self):
        """Deve retryar em caso de timeout."""
        import httpx as httpx_module

        config = AIConfig(enabled=True, api_key="test-key", model="test-model",
                         timeout=1.0, max_retries=2)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openrouter_response()

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx_module.TimeoutException("timeout")
            return mock_response

        with patch.object(client._http, "post", side_effect=side_effect):
            with patch("app.ai.client.time.sleep"):
                response = client.chat(_simple_request())

        assert response.content == "4"
        assert call_count == 2

    def test_retry_provider_500(self):
        """Deve retryar em caso de HTTP 500."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model",
                         max_retries=2)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        error_response = MagicMock()
        error_response.status_code = 500
        error_response.json.return_value = {"error": {"message": "Server error"}}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = _openrouter_response()

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return error_response
            return success_response

        with patch.object(client._http, "post", return_value=success_response):
            with patch("app.ai.client.time.sleep"):
                pass

        # Reset and test properly
        call_count = 0
        client2 = AIClient(config, tracker)

        def side_effect2(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return error_response
            return success_response

        with patch.object(client2._http, "post", side_effect=side_effect2):
            with patch("app.ai.client.time.sleep"):
                response = client2.chat(_simple_request())

        assert response.content == "4"
        assert call_count == 2

    def test_no_retry_429_without_retries(self):
        """429 não deve retryar quando max_retries=0."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limited"}}

        with patch.object(client._http, "post", return_value=mock_response):
            with pytest.raises(AIRateLimitError):
                client.chat(_simple_request())


# ---------------------------------------------------------------------------
# Testes: AIClient - Segurança dos logs
# ---------------------------------------------------------------------------

class TestAIClientSecurity:
    """Testes de segurança - API key não deve aparecer em logs."""

    def test_api_key_nao_aparece_no_repr(self):
        """API key não deve aparecer em repr()."""
        config = AIConfig(enabled=True, api_key="sk-super-secret-key-12345", model="test")
        client = AIClient(config, UsageTracker())
        assert "sk-super-secret" not in repr(client)

    def test_config_repr_seguro(self):
        """AIConfig repr() é seguro."""
        config = AIConfig(api_key="sk-super-secret-key-12345")
        assert "sk-super-secret" not in repr(config)
        assert "sk-super-secret" not in str(config)


# ---------------------------------------------------------------------------
# Testes: AIClient - Context manager
# ---------------------------------------------------------------------------

class TestAIClientContextManager:
    """Testes para uso como context manager."""

    def test_context_manager(self):
        """AIClient deve funcionar como context manager."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model")
        tracker = UsageTracker()

        with AIClient(config, tracker) as client:
            assert client is not None
            assert client.enabled is True

    def test_close(self):
        """close() deve fechar a conexão HTTP."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model")
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        assert client._http is not None
        client.close()
        assert client._http is None


# ---------------------------------------------------------------------------
# Testes: App Factory - AI Client Singleton
# ---------------------------------------------------------------------------

class TestAppFactoryAI:
    """Testes para integração do AI Client na app factory."""

    def test_app_tem_ai_client(self):
        """App deve ter ai_client e ai_tracker."""
        app = create_app("testing")
        assert hasattr(app, "ai_client")
        assert hasattr(app, "ai_tracker")
        assert isinstance(app.ai_client, AIClient)
        assert isinstance(app.ai_tracker, UsageTracker)

    def test_app_ai_client_desabilitado_por_padrao(self):
        """AI client deve estar desabilitado por padrão em teste."""
        app = create_app("testing")
        assert app.ai_client.enabled is False

    def test_app_ai_client_nao_quebra_sem_env(self):
        """App não deve quebrar mesmo sem variáveis de ambiente AI."""
        app = create_app("testing")
        assert app.ai_client is not None
        assert app.ai_tracker is not None


# ---------------------------------------------------------------------------
# Testes: JSON inválido do provider
# ---------------------------------------------------------------------------

class TestAIClientInvalidJSON:
    """Testes para JSON inválido na resposta do provider."""

    def test_resposta_nao_json(self):
        """Resposta que não é JSON deve levantar AIValidationError."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("err", "", 0)

        with patch.object(client._http, "post", return_value=mock_response):
            with pytest.raises(AIValidationError):
                client.chat(_simple_request())


# ---------------------------------------------------------------------------
# Testes: Uso do tracker
# ---------------------------------------------------------------------------

class TestUsageTrackerIntegration:
    """Testes de integração do UsageTracker com AIClient."""

    def test_tracker_registra_sucesso(self):
        """Tracker deve registrar chamada bem-sucedida."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openrouter_response()

        with patch.object(client._http, "post", return_value=mock_response):
            client.chat(_simple_request(), feature="test_feature")

        records = tracker.get_records()
        assert len(records) == 1
        assert records[0].feature == "test_feature"
        assert records[0].model == "openai/gpt-4o-mini"
        assert records[0].input_tokens == 10
        assert records[0].output_tokens == 5
        assert records[0].total_tokens == 15
        assert records[0].status == "success"

    def test_tracker_multiple_calls(self):
        """Tracker deve registrar múltiplas chamadas."""
        config = AIConfig(enabled=True, api_key="test-key", model="test-model", max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openrouter_response()

        with patch.object(client._http, "post", return_value=mock_response):
            client.chat(_simple_request(), feature="f1")
            client.chat(_simple_request(), feature="f2")

        assert len(tracker.get_records()) == 2
        summary = tracker.summary()
        assert summary["total_calls"] == 2
        assert summary["success_calls"] == 2
