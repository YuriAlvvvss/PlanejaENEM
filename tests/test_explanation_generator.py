"""
Testes do Gerador de Explicações - PlanejaENEM 5.0.

Suite completa para explanation_generator.
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
    ExplanationGenerator,
    ExplanationInput,
    ExplanationOutput,
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


def _valid_explanation_input(**kwargs) -> ExplanationInput:
    """ExplanationInput válido para testes."""
    defaults = dict(
        question_id="q123",
        statement="Qual é o resultado de 2 + 2?",
        alternatives={"A": "3", "B": "4", "C": "5", "D": "6", "E": "7"},
        student_answer="B",
        correct_answer="B",
        materia="Matemática",
        assunto="Aritmética",
        dificuldade=1,
    )
    defaults.update(kwargs)
    return ExplanationInput(**defaults)


def _wrong_answer_input() -> ExplanationInput:
    """ExplanationInput com resposta errada."""
    return _valid_explanation_input(student_answer="A", correct_answer="B")


def _correct_answer_input() -> ExplanationInput:
    """ExplanationInput com resposta correta."""
    return _valid_explanation_input(student_answer="B", correct_answer="B")


def _valid_explanation_response() -> dict:
    """Resposta válida da IA para explicação."""
    return {
        "summary": "A soma de 2 + 2 resulta em 4.",
        "concept": "Operação básica de adição.",
        "steps": [
            "Identifique os números: 2 e 2.",
            "Some: 2 + 2 = 4.",
            "Verifique a resposta nas alternativas.",
        ],
        "common_mistake": "Confundir soma com multiplicação.",
        "study_tip": "Pratique tabuada e operações básicas.",
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
# Testes: ExplanationInput
# ---------------------------------------------------------------------------

class TestExplanationInput:
    """Testes para ExplanationInput."""

    def test_created_successfully(self):
        """Deve criar ExplanationInput com todos os campos."""
        inp = _valid_explanation_input()
        assert inp.question_id == "q123"
        assert inp.student_answer == "B"
        assert inp.correct_answer == "B"
        assert inp.materia == "Matemática"

    def test_optional_fields(self):
        """Campos opcionais devem ser None por padrão."""
        inp = _valid_explanation_input()
        assert inp.mastery is None
        assert inp.trend is None
        assert inp.recurring_error is None

    def test_with_optional_fields(self):
        """Campos opcionais devem ser aceitos."""
        inp = _valid_explanation_input(
            mastery=0.75,
            trend="melhorando",
            recurring_error="Confunde adição com subtração",
        )
        assert inp.mastery == 0.75
        assert inp.trend == "melhorando"
        assert inp.recurring_error == "Confunde adição com subtração"

    def test_frozen(self):
        """ExplanationInput deve ser imutável."""
        inp = _valid_explanation_input()
        with pytest.raises(AttributeError):
            inp.question_id = "q999"


# ---------------------------------------------------------------------------
# Testes: ExplanationOutput
# ---------------------------------------------------------------------------

class TestExplanationOutput:
    """Testes para ExplanationOutput."""

    def test_created_successfully(self):
        """Deve criar ExplanationOutput com todos os campos."""
        out = ExplanationOutput(
            summary="Resumo",
            concept="Conceito",
            steps=["Passo 1", "Passo 2"],
            common_mistake="Erro comum",
            study_tip="Dica",
        )
        assert out.summary == "Resumo"
        assert len(out.steps) == 2

    def test_frozen(self):
        """ExplanationOutput deve ser imutável."""
        out = ExplanationOutput(
            summary="S", concept="C", steps=[], common_mistake="", study_tip=""
        )
        with pytest.raises(AttributeError):
            out.summary = "novo"


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Configuração
# ---------------------------------------------------------------------------

class TestExplanationGeneratorConfig:
    """Testes para configuração do gerador."""

    def test_repr(self):
        """repr não deve expor dados sensíveis."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client)
        r = repr(gen)
        assert "ExplanationGenerator" in r
        assert "cache_ttl" in r
        assert "max_tokens" in r

    def test_custom_config(self):
        """Config customizada deve ser aceita."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=1800, max_tokens=400)
        assert gen._cache_ttl == 1800
        assert gen._max_tokens == 400

    def test_default_config(self):
        """Config padrão deve ter valores razoáveis."""
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client)
        assert gen._cache_ttl == 3600
        assert gen._max_tokens == 800


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Client desabilitado
# ---------------------------------------------------------------------------

class TestExplanationGeneratorDisabled:
    """Testes para quando a IA está desligada."""

    def test_client_disabled_returns_fallback(self):
        """Client desabilitado deve retornar fallback."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client)

        inp = _wrong_answer_input()
        result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)
        assert "B" in result.summary
        assert "A" in result.summary
        assert result.concept != ""
        assert len(result.steps) > 0

    def test_client_disabled_correct_answer_fallback(self):
        """Fallback para resposta correta deve ser positivo."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client)

        inp = _correct_answer_input()
        result = gen.generate(inp)

        assert "acertou" in result.summary.lower()


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Sucesso
# ---------------------------------------------------------------------------

class TestExplanationGeneratorSuccess:
    """Testes para geração bem-sucedida."""

    def test_generate_wrong_answer(self):
        """Geração para resposta errada deve retornar explicação."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)
        assert result.summary != ""
        assert result.concept != ""
        assert len(result.steps) > 0

    def test_generate_correct_answer(self):
        """Geração para resposta correta deve retornar explicação."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _correct_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)

    def test_generate_with_optional_fields(self):
        """Geração com campos opcionais deve funcionar."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _valid_explanation_input(
            mastery=0.65,
            trend="estavel",
            recurring_error="Erro recorrente",
        )
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Fallback
# ---------------------------------------------------------------------------

class TestExplanationGeneratorFallback:
    """Testes para fallback quando a IA falha."""

    def test_provider_error_returns_fallback(self):
        """Erro do provider deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()

        with patch.object(
            client, "chat_structured", side_effect=AIProviderError("Provider offline")
        ):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)
        assert "B" in result.summary

    def test_validation_error_returns_fallback(self):
        """Erro de validação deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()

        with patch.object(
            client, "chat_structured", side_effect=AIValidationError("Schema inválido")
        ):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)

    def test_generic_exception_returns_fallback(self):
        """Exceção genérica deve retornar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()

        with patch.object(
            client, "chat_structured", side_effect=RuntimeError("Erro inesperado")
        ):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)

    def test_fallback_correct_answer_content(self):
        """Fallback para resposta correta deve conter gabarito."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client)

        inp = _correct_answer_input()
        result = gen.generate(inp)

        assert "B" in result.summary
        assert "acertou" in result.summary.lower()
        assert inp.assunto in result.concept

    def test_fallback_wrong_answer_content(self):
        """Fallback para resposta errada deve conter gabarito."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client)

        inp = _wrong_answer_input()
        result = gen.generate(inp)

        assert "B" in result.summary
        assert "A" in result.summary
        assert "errou" in result.summary.lower()


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Cache
# ---------------------------------------------------------------------------

class TestExplanationGeneratorCache:
    """Testes para cache de explicações."""

    def test_cache_hit(self):
        """Segunda chamada com mesmos parâmetros deve usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=60)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            result1 = gen.generate(inp)
            result2 = gen.generate(inp)

        assert mock_cs.call_count == 1
        assert result1.summary == result2.summary

    def test_cache_different_answers(self):
        """Respostas diferentes não devem usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=60)

        inp1 = _valid_explanation_input(student_answer="A", correct_answer="B")
        inp2 = _valid_explanation_input(student_answer="C", correct_answer="B")
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(inp1)
            gen.generate(inp2)

        assert mock_cs.call_count == 2

    def test_cache_expiry(self):
        """Cache deve expirar após TTL."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            gen.generate(inp)
            gen.generate(inp)

        assert mock_cs.call_count == 2

    def test_clear_cache(self):
        """clear_cache() deve limpar o cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=60)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

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
        gen = ExplanationGenerator(client, cache_ttl=60)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            gen.generate(inp)

        cached = gen.get_cached(inp)
        assert cached is not None
        assert cached.summary != ""

    def test_get_cached_expired(self):
        """get_cached() deve retornar None se expirado."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            gen.generate(inp)

        cached = gen.get_cached(inp)
        assert cached is None


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Sanitização
# ---------------------------------------------------------------------------

class TestExplanationGeneratorSanitization:
    """Testes para sanitização de output."""

    def test_html_stripped(self):
        """HTML deve ser removido da resposta."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        dirty_response = {
            "summary": "<script>alert('xss')</script>Resposta correta",
            "concept": "<b>Negrito</b> e <i>itálico</i>",
            "steps": ["<img src=x onerror=alert(1)>Passo 1"],
            "common_mistake": "<a href='javascript:alert(1)'>link</a>",
            "study_tip": "Dica normal",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert "<script>" not in result.summary
        assert "<b>" not in result.concept
        assert "<img" not in result.steps[0]
        assert "<a " not in result.common_mistake

    def test_html_entities_decoded(self):
        """Entidades HTML devem ser decodificadas."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        dirty_response = {
            "summary": "2 + 2 = 4 &amp; é simples",
            "concept": "Conceito",
            "steps": ["Passo"],
            "common_mistake": "Erro",
            "study_tip": "Dica",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert "&amp;" not in result.summary
        assert "4 & é simples" in result.summary

    def test_whitespace_normalized(self):
        """Whitespace extra deve ser normalizado."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        dirty_response = {
            "summary": "  Resposta   com   espaços  ",
            "concept": "Conceito",
            "steps": ["Passo"],
            "common_mistake": "Erro",
            "study_tip": "Dica",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert result.summary == "Resposta com espaços"

    def test_steps_list_handled(self):
        """Steps não-lista devem ser convertidos."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        dirty_response = {
            "summary": "Resumo",
            "concept": "Conceito",
            "steps": "Step único como string",
            "common_mistake": "Erro",
            "study_tip": "Dica",
        }
        mock_resp = _make_structured_response(dirty_response)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result.steps, list)


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Prompt
# ---------------------------------------------------------------------------

class TestExplanationGeneratorPrompt:
    """Testes para construção de prompts."""

    def test_prompt_wrong_answer(self):
        """Prompt para errada deve mencionar erro."""
        from app.ai.explanation_generator import _build_explanation_prompt

        inp = _wrong_answer_input()
        messages = _build_explanation_prompt(inp)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "ERROU" in messages[1]["content"]
        assert inp.correct_answer in messages[1]["content"]
        assert inp.student_answer in messages[1]["content"]

    def test_prompt_correct_answer(self):
        """Prompt para correta deve mencionar acerto."""
        from app.ai.explanation_generator import _build_explanation_prompt

        inp = _correct_answer_input()
        messages = _build_explanation_prompt(inp)

        assert "ACERTOU" in messages[1]["content"]

    def test_prompt_includes_context(self):
        """Prompt deve incluir contexto da questão."""
        from app.ai.explanation_generator import _build_explanation_prompt

        inp = _valid_explanation_input(
            mastery=0.75, trend="melhorando", recurring_error="Erro X"
        )
        messages = _build_explanation_prompt(inp)
        user_content = messages[1]["content"]

        assert "Matemática" in user_content
        assert "Aritmética" in user_content
        assert "75%" in user_content
        assert "melhorando" in user_content
        assert "Erro X" in user_content

    def test_prompt_includes_alternatives(self):
        """Prompt deve incluir todas as alternativas."""
        from app.ai.explanation_generator import _build_explanation_prompt

        inp = _valid_explanation_input()
        messages = _build_explanation_prompt(inp)
        user_content = messages[1]["content"]

        for letter in ["A", "B", "C", "D", "E"]:
            assert f"{letter}:" in user_content


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Validação de schema
# ---------------------------------------------------------------------------

class TestExplanationGeneratorSchemaValidation:
    """Testes para validação de schema da resposta."""

    def test_missing_required_fields(self):
        """Campos obrigatórios ausentes devem usar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        incomplete = {"summary": "Apenas sumário"}
        mock_resp = _make_structured_response(incomplete)

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)

    def test_empty_response(self):
        """Resposta vazia deve usar fallback."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response({})

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)


# ---------------------------------------------------------------------------
# Testes: ExplanationGenerator - Integração
# ---------------------------------------------------------------------------

class TestExplanationGeneratorIntegration:
    """Testes de integração."""

    def test_full_flow_wrong_answer(self):
        """Fluxo completo: input -> prompt -> client -> output."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _wrong_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp) as mock_cs:
            result = gen.generate(inp)

        assert mock_cs.call_count == 1
        call_args = mock_cs.call_args
        assert call_args[1]["feature"] == "explanation"
        assert "summary" in call_args[1]["expected_keys"]

        assert isinstance(result, ExplanationOutput)
        assert result.summary != ""
        assert result.concept != ""
        assert len(result.steps) > 0

    def test_full_flow_correct_answer(self):
        """Fluxo completo para resposta correta."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client, cache_ttl=0)

        inp = _correct_answer_input()
        mock_resp = _make_structured_response(_valid_explanation_response())

        with patch.object(client, "chat_structured", return_value=mock_resp):
            result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)

    def test_fallback_no_api_call(self):
        """Fallback não deve fazer chamada à API."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = ExplanationGenerator(client)

        inp = _wrong_answer_input()
        result = gen.generate(inp)

        assert isinstance(result, ExplanationOutput)
        assert len(tracker.get_records()) == 0
