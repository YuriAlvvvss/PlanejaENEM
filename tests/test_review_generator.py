"""
Testes do Gerador de Revisões - PlanejaENEM 5.0.

Suite completa para review_generator.
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
    ReviewGenerator,
    ReviewInput,
    ReviewOutput,
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


def _valid_review_input(**kwargs) -> ReviewInput:
    """ReviewInput válido para testes."""
    defaults = dict(
        materia="Matemática",
        assunto="Equações do 2º grau",
        mastery=0.65,
        confidence=0.70,
        weak_concepts=["Discriminante", "Relação de Bhaskara"],
        recent_errors=["Errou cálculo de delta", "Confundiu sinal de"],
    )
    defaults.update(kwargs)
    return ReviewInput(**defaults)


def _minimal_review_input() -> ReviewInput:
    """ReviewInput mínimo (sem campos opcionais)."""
    return ReviewInput(
        materia="História",
        assunto="Revolução Francesa",
        mastery=0.40,
        confidence=0.50,
        weak_concepts=[],
        recent_errors=[],
    )


def _valid_review_response() -> dict:
    """Resposta válida da IA para revisão."""
    return {
        "title": "Revisão: Equações do 2º grau",
        "summary": "Equações do 2º grau são da forma ax² + bx + c = 0.",
        "key_concepts": ["Discriminante", "Bhaskara", "Delta"],
        "worked_example": "Resolva x² - 5x + 6 = 0: Δ = 25 - 24 = 1, x = (5±1)/2.",
        "common_mistakes": ["Esquecer o sinal de b no Bhaskara", "Calcular delta errado"],
        "quick_check": "Resolva x² - 3x + 2 = 0 sem olhar a resposta.",
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
# Testes: ReviewInput
# ---------------------------------------------------------------------------

class TestReviewInput:
    """Testes para ReviewInput."""

    def test_created_successfully(self):
        """Deve criar ReviewInput com todos os campos."""
        inp = _valid_review_input()
        assert inp.materia == "Matemática"
        assert inp.assunto == "Equações do 2º grau"
        assert inp.mastery == 0.65
        assert inp.confidence == 0.70

    def test_optional_fields(self):
        """Campos opcionais devem ser listas vazias por padrão."""
        inp = _valid_review_input()
        assert isinstance(inp.weak_concepts, list)
        assert isinstance(inp.recent_errors, list)

    def test_with_optional_fields(self):
        """Campos opcionais devem ser aceitos."""
        inp = _valid_review_input(
            weak_concepts=["Conceito A", "Conceito B"],
            recent_errors=["Erro 1", "Erro 2"],
        )
        assert len(inp.weak_concepts) == 2
        assert len(inp.recent_errors) == 2

    def test_frozen(self):
        """ReviewInput deve ser imutável."""
        inp = _valid_review_input()
        with pytest.raises(AttributeError):
            inp.materia = "Português"


# ---------------------------------------------------------------------------
# Testes: ReviewOutput
# ---------------------------------------------------------------------------

class TestReviewOutput:
    """Testes para ReviewOutput."""

    def test_created_successfully(self):
        """Deve criar ReviewOutput com todos os campos."""
        out = ReviewOutput(
            title="Título",
            summary="Resumo",
            key_concepts=["Conceito 1"],
            worked_example="Exemplo",
            common_mistakes=["Erro"],
            quick_check="Pergunta",
        )
        assert out.title == "Título"
        assert out.summary == "Resumo"
        assert len(out.key_concepts) == 1

    def test_frozen(self):
        """ReviewOutput deve ser imutável."""
        out = ReviewOutput(
            title="T", summary="S", key_concepts=[],
            worked_example="E", common_mistakes=[], quick_check="Q",
        )
        with pytest.raises(AttributeError):
            out.title = "novo"


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Configuração
# ---------------------------------------------------------------------------

class TestReviewGeneratorConfig:
    """Testes para configuração do gerador."""

    def test_repr(self):
        """repr não deve expor dados sensíveis."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client)
        r = repr(gen)
        assert "ReviewGenerator" in r
        assert "cache_ttl" in r
        assert "default_max_tokens" in r

    def test_custom_config(self):
        """Config customizada deve ser aceita."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=1800, default_max_tokens=600)
        assert gen._cache_ttl == 1800
        assert gen._default_max_tokens == 600

    def test_default_config(self):
        """Config padrão deve ter valores razoáveis."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client)
        assert gen._cache_ttl == 3600
        assert gen._default_max_tokens == 1000


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Client desabilitado
# ---------------------------------------------------------------------------

class TestReviewGeneratorDisabled:
    """Testes para quando a IA está desligada."""

    def test_client_disabled_returns_fallback(self):
        """Client desabilitado deve retornar fallback."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client)

        inp = _valid_review_input()
        result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)
        assert result.title != ""
        assert result.summary != ""
        assert len(result.key_concepts) > 0

    def test_client_disabled_minimal_input_fallback(self):
        """Fallback com input mínimo deve funcionar."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client)

        inp = _minimal_review_input()
        result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)
        assert "Revolução Francesa" in result.title


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Sucesso
# ---------------------------------------------------------------------------

class TestReviewGeneratorSuccess:
    """Testes para geração bem-sucedida."""

    def test_generate_5_minutes(self):
        """Geração para 5 minutos deve retornar revisão curta."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input(duration_minutes=5)
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)
        assert result.title != ""
        assert result.summary != ""

    def test_generate_10_minutes(self):
        """Geração para 10 minutos deve retornar revisão."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input(duration_minutes=10)
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)

    def test_generate_20_minutes(self):
        """Geração para 20 minutos deve retornar revisão completa."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input(duration_minutes=20)
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)

    def test_generate_minimal_input(self):
        """Geração com input mínimo deve funcionar."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _minimal_review_input()
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Fallback
# ---------------------------------------------------------------------------

class TestReviewGeneratorFallback:
    """Testes para fallback quando a IA falha."""

    def test_provider_error_returns_fallback(self):
        """Erro do provider deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()

        with patch.object(
            client, "chat_structured", side_effect=AIProviderError("Provider offline")
        ):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)
        assert result.title != ""

    def test_validation_error_returns_fallback(self):
        """Erro de validação deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()

        with patch.object(
            client, "chat_structured", side_effect=AIValidationError("Schema inválido")
        ):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)

    def test_generic_exception_returns_fallback(self):
        """Exceção genérica deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()

        with patch.object(
            client, "chat_structured", side_effect=RuntimeError("Erro inesperado")
        ):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)

    def test_fallback_content_with_weak_concepts(self):
        """Fallback deve incluir conceitos fracos no conteúdo."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client)

        inp = _valid_review_input()
        result = gen.generate(inp)

        assert result.key_concepts[0] == "Discriminante"
        assert result.key_concepts[1] == "Relação de Bhaskara"
        assert "Equações do 2º grau" in result.summary

    def test_fallback_content_without_weak_concepts(self):
        """Fallback sem conceitos fracos deve usar assunto."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client)

        inp = _minimal_review_input()
        result = gen.generate(inp)

        assert "Revolução Francesa" in result.key_concepts[0]


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Cache
# ---------------------------------------------------------------------------

class TestReviewGeneratorCache:
    """Testes para cache de revisões."""

    def test_cache_hit(self):
        """Segunda chamada com mesmos parâmetros deve usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=60)

        inp = _valid_review_input()
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            result1 = gen.generate(inp)
            result2 = gen.generate(inp)

        assert mock_cs.call_count == 1
        assert result1.title == result2.title

    def test_cache_different_topics(self):
        """Tópicos diferentes não devem usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=60)

        inp1 = _valid_review_input(assunto="Equações do 2º grau")
        inp2 = _valid_review_input(assunto="Funções")
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(inp1)
            gen.generate(inp2)

        assert mock_cs.call_count == 2

    def test_cache_expiry(self):
        """Cache deve expirar após TTL."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(inp)
            gen.generate(inp)

        assert mock_cs.call_count == 2

    def test_clear_cache(self):
        """clear_cache() deve limpar o cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=60)

        inp = _valid_review_input()
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(inp)
            assert mock_cs.call_count == 1

            gen.clear_cache()

            gen.generate(inp)
            assert mock_cs.call_count == 2

    def test_get_cached(self):
        """get_cached() deve retornar cache válido."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=60)

        inp = _valid_review_input()
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            gen.generate(inp)

        cached = gen.get_cached(inp)
        assert cached is not None
        assert cached.title != ""

    def test_get_cached_expired(self):
        """get_cached() deve retornar None se expirado."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            gen.generate(inp)

        cached = gen.get_cached(inp)
        assert cached is None


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Sanitização
# ---------------------------------------------------------------------------

class TestReviewGeneratorSanitization:
    """Testes para sanitização de output."""

    def test_html_stripped(self):
        """HTML deve ser removido da resposta."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        dirty_response = {
            "title": "<script>alert('xss')</script>Revisão",
            "summary": "<b>Negrito</b> e <i>itálico</i>",
            "key_concepts": ["<img src=x onerror=alert(1)>Conceito"],
            "worked_example": "<a href='javascript:alert(1)'>Exemplo</a>",
            "common_mistakes": ["Erro normal"],
            "quick_check": "Pergunta normal",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert "<script>" not in result.title
        assert "<b>" not in result.summary
        assert "<img" not in result.key_concepts[0]
        assert "<a " not in result.worked_example

    def test_html_entities_decoded(self):
        """Entidades HTML devem ser decodificadas."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        dirty_response = {
            "title": "Revisão &amp; Estudo",
            "summary": "Resumo com &lt;links&gt;",
            "key_concepts": ["Conceito"],
            "worked_example": "Exemplo",
            "common_mistakes": ["Erro"],
            "quick_check": "Pergunta",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert "&amp;" not in result.title
        assert "&lt;" not in result.summary

    def test_whitespace_normalized(self):
        """Whitespace extra deve ser normalizado."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        dirty_response = {
            "title": "  Revisão   com   espaços  ",
            "summary": "Resumo",
            "key_concepts": ["Conceito"],
            "worked_example": "Exemplo",
            "common_mistakes": ["Erro"],
            "quick_check": "Pergunta",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert result.title == "Revisão com espaços"

    def test_list_fields_handled(self):
        """Campos de lista não-lista devem ser convertidos."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        dirty_response = {
            "title": "Revisão",
            "summary": "Resumo",
            "key_concepts": "Conceito único como string",
            "worked_example": "Exemplo",
            "common_mistakes": "Erro único",
            "quick_check": "Pergunta",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result.key_concepts, list)
        assert isinstance(result.common_mistakes, list)


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Prompt
# ---------------------------------------------------------------------------

class TestReviewGeneratorPrompt:
    """Testes para construção de prompts."""

    def test_prompt_includes_context(self):
        """Prompt deve incluir contexto da revisão."""
        from app.ai.review_generator import _build_review_prompt

        inp = _valid_review_input()
        messages = _build_review_prompt(inp)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

        user_content = messages[1]["content"]
        assert "Matemática" in user_content
        assert "Equações do 2º grau" in user_content
        assert "65%" in user_content
        assert "70%" in user_content

    def test_prompt_includes_weak_concepts(self):
        """Prompt deve incluir conceitos fracos."""
        from app.ai.review_generator import _build_review_prompt

        inp = _valid_review_input()
        messages = _build_review_prompt(inp)
        user_content = messages[1]["content"]

        assert "Discriminante" in user_content
        assert "Bhaskara" in user_content

    def test_prompt_includes_recent_errors(self):
        """Prompt deve incluir erros recentes."""
        from app.ai.review_generator import _build_review_prompt

        inp = _valid_review_input()
        messages = _build_review_prompt(inp)
        user_content = messages[1]["content"]

        assert "delta" in user_content.lower()

    def test_prompt_duration_5_min(self):
        """Prompt para 5 min deve mencionar duração."""
        from app.ai.review_generator import _build_review_prompt

        inp = _valid_review_input(duration_minutes=5)
        messages = _build_review_prompt(inp)
        system_content = messages[0]["content"]

        assert "5 minutos" in system_content

    def test_prompt_duration_20_min(self):
        """Prompt para 20 min deve mencionar duração."""
        from app.ai.review_generator import _build_review_prompt

        inp = _valid_review_input(duration_minutes=20)
        messages = _build_review_prompt(inp)
        system_content = messages[0]["content"]

        assert "20 minutos" in system_content


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Validação de schema
# ---------------------------------------------------------------------------

class TestReviewGeneratorSchemaValidation:
    """Testes para validação de schema da resposta."""

    def test_missing_required_fields(self):
        """Campos obrigatórios ausentes devem usar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        incomplete = {"title": "Apenas título"}
        mock_resp = _make_structured_response(incomplete)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)

    def test_empty_response(self):
        """Resposta vazia deve usar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        mock_resp = _make_structured_response({})

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Duração
# ---------------------------------------------------------------------------

class TestReviewGeneratorDuration:
    """Testes para validação de duração."""

    def test_duration_normalization_below_5(self):
        """Duração abaixo de 5 deve ser normalizada para 5."""
        from app.ai.review_generator import _validate_duration
        assert _validate_duration(3) == 5

    def test_duration_normalization_between_5_and_10(self):
        """Duração entre 5 e 10 deve ser normalizada para 10."""
        from app.ai.review_generator import _validate_duration
        assert _validate_duration(7) == 10

    def test_duration_normalization_above_20(self):
        """Duração acima de 20 deve ser normalizada para 20."""
        from app.ai.review_generator import _validate_duration
        assert _validate_duration(30) == 20

    def test_duration_exact_values(self):
        """Durações exatas (5, 10, 20) devem ser preservadas."""
        from app.ai.review_generator import _validate_duration
        assert _validate_duration(5) == 5
        assert _validate_duration(10) == 10
        assert _validate_duration(20) == 20


# ---------------------------------------------------------------------------
# Testes: ReviewGenerator - Integração
# ---------------------------------------------------------------------------

class TestReviewGeneratorIntegration:
    """Testes de integração."""

    def test_full_flow(self):
        """Fluxo completo: input -> prompt -> client -> output."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client, cache_ttl=0)

        inp = _valid_review_input()
        mock_resp = _make_structured_response(_valid_review_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            result = gen.generate(inp)

        assert mock_cs.call_count == 1
        call_args = mock_cs.call_args
        assert call_args[1]["feature"] == "review"
        assert "title" in call_args[1]["expected_keys"]

        assert isinstance(result, ReviewOutput)
        assert result.title != ""
        assert result.summary != ""
        assert len(result.key_concepts) > 0

    def test_fallback_no_api_call(self):
        """Fallback não deve fazer chamada à API."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ReviewGenerator(client)

        inp = _valid_review_input()
        result = gen.generate(inp)

        assert isinstance(result, ReviewOutput)
        assert len(tracker.get_records()) == 0
