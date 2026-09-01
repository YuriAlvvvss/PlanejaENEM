"""
Testes do Gerador de Feedback - PlanejaENEM 5.0.

Suite completa para feedback_generator.
Todos os testes usam mocks — nenhuma chamada real ao OpenRouter.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.ai import (
    AIClient,
    AIConfig,
    AIDisabledError,
    AIValidationError,
    FeedbackGenerator,
    FeedbackOutput,
    PerformanceData,
    UsageTracker,
)
from app.ai.exceptions import AIProviderError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enabled_config(**kwargs) -> AIConfig:
    """Config AI habilitada para testes."""
    defaults = dict(
        enabled=True,
        api_key="test-key",
        model="openai/gpt-4o-mini",
        max_retries=0,
        timeout=5.0,
    )
    defaults.update(kwargs)
    return AIConfig(**defaults)


def _valid_performance_data(**kwargs) -> PerformanceData:
    """PerformanceData válido para testes."""
    defaults = dict(
        accuracy=0.72,
        mastery=0.65,
        confidence=0.80,
        trend="melhorando",
        strong_points=["Álgebra", "Geometria"],
        weak_points=["Estatística", "Trigonometria"],
        recent_performance=[0.60, 0.65, 0.70, 0.72, 0.75],
        historical_performance=[0.55, 0.58, 0.62, 0.68, 0.72],
    )
    defaults.update(kwargs)
    return PerformanceData(**defaults)


def _valid_feedback_response() -> dict:
    """Resposta válida da IA para feedback."""
    return {
        "summary": "Seu desempenho está melhorando. Acurácia de 72%.",
        "strengths": ["Álgebra é um ponto forte", "Boa evolução em Geometria"],
        "weaknesses": ["Estatística precisa de atenção", "Trigonometria precisa de prática"],
        "advice": "Foque nos pontos fracos mas mantenha a prática nos fortes.",
        "next_step": "Pratique 10 questões de Estatística esta semana.",
    }


def _make_structured_response(data: dict) -> MagicMock:
    """Cria StructuredChatResponse simulado."""
    resp = MagicMock()
    resp.data = data
    resp.model = "openai/gpt-4o-mini"
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = 50
    resp.usage.completion_tokens = 200
    resp.usage.total_tokens = 250
    resp.latency_ms = 500.0
    return resp


# ---------------------------------------------------------------------------
# Testes: PerformanceData
# ---------------------------------------------------------------------------

class TestPerformanceData:
    """Testes para PerformanceData."""

    def test_created_successfully(self):
        """Deve criar PerformanceData com todos os campos."""
        data = _valid_performance_data()
        assert data.accuracy == 0.72
        assert data.mastery == 0.65
        assert data.confidence == 0.80
        assert data.trend == "melhorando"
        assert len(data.strong_points) == 2
        assert len(data.weak_points) == 2
        assert len(data.recent_performance) == 5
        assert len(data.historical_performance) == 5

    def test_frozen(self):
        """PerformanceData deve ser imutável."""
        data = _valid_performance_data()
        with pytest.raises(AttributeError):
            data.accuracy = 0.90

    def test_empty_lists(self):
        """Listas vazias devem ser aceitas."""
        data = PerformanceData(
            accuracy=0.5,
            mastery=0.5,
            confidence=0.5,
            trend="estavel",
            strong_points=[],
            weak_points=[],
            recent_performance=[],
            historical_performance=[],
        )
        assert data.strong_points == []
        assert data.weak_points == []


# ---------------------------------------------------------------------------
# Testes: FeedbackOutput
# ---------------------------------------------------------------------------

class TestFeedbackOutput:
    """Testes para FeedbackOutput."""

    def test_created_successfully(self):
        """Deve criar FeedbackOutput com todos os campos."""
        out = FeedbackOutput(
            summary="Resumo",
            strengths=["Forte 1"],
            weaknesses=["Fraco 1"],
            advice="Conselho",
            next_step="Próximo passo",
        )
        assert out.summary == "Resumo"
        assert len(out.strengths) == 1
        assert len(out.weaknesses) == 1

    def test_frozen(self):
        """FeedbackOutput deve ser imutável."""
        out = FeedbackOutput(
            summary="S", strengths=[], weaknesses=[], advice="", next_step=""
        )
        with pytest.raises(AttributeError):
            out.summary = "novo"


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Configuração
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorConfig:
    """Testes para configuração do gerador."""

    def test_repr(self):
        """repr não deve expor dados sensíveis."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)
        r = repr(gen)
        assert "FeedbackGenerator" in r
        assert "cache_ttl" in r
        assert "max_tokens" in r

    def test_custom_config(self):
        """Config customizada deve ser aceita."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=1800, max_tokens=400)
        assert gen._cache_ttl == 1800
        assert gen._max_tokens == 400

    def test_default_config(self):
        """Config padrão deve ter valores razoáveis."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)
        assert gen._cache_ttl == 3600
        assert gen._max_tokens == 800


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Client desabilitado
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorDisabled:
    """Testes para quando a IA está desligada."""

    def test_client_disabled_returns_fallback(self):
        """Client desabilitado deve retornar fallback."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)

        data = _valid_performance_data()
        result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)
        assert "72%" in result.summary
        assert len(result.strengths) > 0
        assert len(result.weaknesses) > 0
        assert result.advice != ""
        assert result.next_step != ""

    def test_fallback_trend_melhorando(self):
        """Fallback deve descrever tendência melhorando."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)

        data = _valid_performance_data(trend="melhorando")
        result = gen.generate(data)

        assert "melhorando" in result.summary.lower()

    def test_fallback_trend_estavel(self):
        """Fallback deve descrever tendência estável."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)

        data = _valid_performance_data(trend="estavel")
        result = gen.generate(data)

        assert "estável" in result.summary.lower()

    def test_fallback_trend_piorando(self):
        """Fallback deve descrever tendência em queda."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)

        data = _valid_performance_data(trend="piorando")
        result = gen.generate(data)

        assert "queda" in result.summary.lower()

    def test_fallback_empty_points(self):
        """Fallback com listas vazias deve usar defaults."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)

        data = _valid_performance_data(strong_points=[], weak_points=[])
        result = gen.generate(data)

        assert len(result.strengths) > 0
        assert len(result.weaknesses) > 0


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Sucesso
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorSuccess:
    """Testes para geração bem-sucedida."""

    def test_generate_success(self):
        """Geração deve retornar feedback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)
        assert result.summary != ""
        assert len(result.strengths) > 0
        assert len(result.weaknesses) > 0
        assert result.advice != ""
        assert result.next_step != ""

    def test_generate_minimal_data(self):
        """Geração com dados mínimos deve funcionar."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = PerformanceData(
            accuracy=0.5,
            mastery=0.5,
            confidence=0.5,
            trend="estavel",
            strong_points=[],
            weak_points=[],
            recent_performance=[0.5],
            historical_performance=[0.5],
        )
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Fallback
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorFallback:
    """Testes para fallback quando a IA falha."""

    def test_provider_error_returns_fallback(self):
        """Erro do provider deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()

        with patch.object(
            client, "chat_structured", side_effect=AIProviderError("Provider offline")
        ):
            result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)
        assert "72%" in result.summary

    def test_validation_error_returns_fallback(self):
        """Erro de validação deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()

        with patch.object(
            client, "chat_structured", side_effect=AIValidationError("Schema inválido")
        ):
            result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)

    def test_generic_exception_returns_fallback(self):
        """Exceção genérica deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()

        with patch.object(
            client, "chat_structured", side_effect=RuntimeError("Erro inesperado")
        ):
            result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Cache
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorCache:
    """Testes para cache de feedback."""

    def test_cache_hit(self):
        """Segunda chamada com mesmos dados deve usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=60)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            result1 = gen.generate(data)
            result2 = gen.generate(data)

        assert mock_cs.call_count == 1
        assert result1.summary == result2.summary

    def test_cache_different_data(self):
        """Dados diferentes não devem usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=60)

        data1 = _valid_performance_data(accuracy=0.72)
        data2 = _valid_performance_data(accuracy=0.85)
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(data1)
            gen.generate(data2)

        assert mock_cs.call_count == 2

    def test_cache_expiry(self):
        """Cache deve expirar após TTL."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(data)
            gen.generate(data)

        assert mock_cs.call_count == 2

    def test_clear_cache(self):
        """clear_cache() deve limpar o cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=60)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(data)
            assert mock_cs.call_count == 1

            gen.clear_cache()

            gen.generate(data)
            assert mock_cs.call_count == 2

    def test_get_cached(self):
        """get_cached() deve retornar cache válido."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=60)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            gen.generate(data)

        cached = gen.get_cached(data)
        assert cached is not None
        assert cached.summary != ""

    def test_get_cached_expired(self):
        """get_cached() deve retornar None se expirado."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            gen.generate(data)

        cached = gen.get_cached(data)
        assert cached is None


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Sanitização
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorSanitization:
    """Testes para sanitização de output."""

    def test_html_stripped(self):
        """HTML deve ser removido da resposta."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        dirty_response = {
            "summary": "<script>alert('xss')</script>Resumo",
            "strengths": ["<b>Forte</b>"],
            "weaknesses": ["<i>Fraco</i>"],
            "advice": "<a href='javascript:alert(1)'>Conselho</a>",
            "next_step": "Próximo passo",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert "<script>" not in result.summary
        assert "<b>" not in result.strengths[0]
        assert "<i>" not in result.weaknesses[0]
        assert "<a " not in result.advice

    def test_html_entities_decoded(self):
        """Entidades HTML devem ser decodificadas."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        dirty_response = {
            "summary": "72% &amp; melhorando",
            "strengths": [],
            "weaknesses": [],
            "advice": "Conselho",
            "next_step": "Próximo",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert "&amp;" not in result.summary
        assert "72% & melhorando" in result.summary

    def test_whitespace_normalized(self):
        """Whitespace extra deve ser normalizado."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        dirty_response = {
            "summary": "  Resumo   com   espaços  ",
            "strengths": [],
            "weaknesses": [],
            "advice": "Conselho",
            "next_step": "Próximo",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert result.summary == "Resumo com espaços"

    def test_strengths_not_list_handled(self):
        """Strengths não-lista devem ser convertidos."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        dirty_response = {
            "summary": "Resumo",
            "strengths": "Ponto forte único",
            "weaknesses": [],
            "advice": "Conselho",
            "next_step": "Próximo",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert isinstance(result.strengths, list)


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Prompt
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorPrompt:
    """Testes para construção de prompts."""

    def test_prompt_includes_stats(self):
        """Prompt deve incluir estatísticas do backend."""
        from app.ai.feedback_generator import _build_feedback_prompt

        data = _valid_performance_data()
        messages = _build_feedback_prompt(data)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

        user_content = messages[1]["content"]
        assert "72%" in user_content
        assert "65%" in user_content
        assert "80%" in user_content
        assert "melhorando" in user_content

    def test_prompt_includes_points(self):
        """Prompt deve incluir pontos fortes e fracos."""
        from app.ai.feedback_generator import _build_feedback_prompt

        data = _valid_performance_data()
        messages = _build_feedback_prompt(data)
        user_content = messages[1]["content"]

        assert "Álgebra" in user_content
        assert "Geometria" in user_content
        assert "Estatística" in user_content
        assert "Trigonometria" in user_content

    def test_prompt_includes_performance_history(self):
        """Prompt deve incluir histórico de desempenho."""
        from app.ai.feedback_generator import _build_feedback_prompt

        data = _valid_performance_data()
        messages = _build_feedback_prompt(data)
        user_content = messages[1]["content"]

        assert "60%" in user_content
        assert "75%" in user_content

    def test_prompt_empty_points(self):
        """Prompt com listas vazias deve funcionar."""
        from app.ai.feedback_generator import _build_feedback_prompt

        data = _valid_performance_data(strong_points=[], weak_points=[])
        messages = _build_feedback_prompt(data)
        user_content = messages[1]["content"]

        assert "Nenhum identificado" in user_content


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Validação de schema
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorSchemaValidation:
    """Testes para validação de schema da resposta."""

    def test_missing_required_fields(self):
        """Campos obrigatórios ausentes devem usar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        incomplete = {"summary": "Apenas sumário"}
        mock_resp = _make_structured_response(incomplete)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)

    def test_empty_response(self):
        """Resposta vazia deve usar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        mock_resp = _make_structured_response({})

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)


# ---------------------------------------------------------------------------
# Testes: FeedbackGenerator - Integração
# ---------------------------------------------------------------------------

class TestFeedbackGeneratorIntegration:
    """Testes de integração."""

    def test_full_flow(self):
        """Fluxo completo: data -> prompt -> client -> output."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=0)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            result = gen.generate(data)

        assert mock_cs.call_count == 1
        call_args = mock_cs.call_args
        assert call_args[1]["feature"] == "feedback"
        assert "summary" in call_args[1]["expected_keys"]

        assert isinstance(result, FeedbackOutput)
        assert result.summary != ""
        assert len(result.strengths) > 0
        assert len(result.weaknesses) > 0
        assert result.advice != ""
        assert result.next_step != ""

    def test_fallback_no_api_call(self):
        """Fallback não deve fazer chamada à API."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client)

        data = _valid_performance_data()
        result = gen.generate(data)

        assert isinstance(result, FeedbackOutput)
        assert len(tracker.get_records()) == 0

    def test_cache_after_success(self):
        """Cache deve ser preenchido após sucesso."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = FeedbackGenerator(client, cache_ttl=60)

        data = _valid_performance_data()
        mock_resp = _make_structured_response(_valid_feedback_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            gen.generate(data)

        assert len(gen._cache) == 1
        cached = gen.get_cached(data)
        assert cached is not None
