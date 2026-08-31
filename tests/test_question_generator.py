"""
Testes do Gerador de Questões - PlanejaENEM 5.0.

Suite completa para prompts, validadores e question_generator.
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
    GeneratedQuestion,
    QuestionGenerator,
    QuestionGeneratorConfig,
    PROMPT_VERSION,
    ValidationResult,
    UsageTracker,
    validate_question,
    validate_question_batch,
    sanitize_question,
)
from app.ai.prompts import build_question_generation_prompt, build_single_question_prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_question_data() -> dict:
    """Dicionário com questão válida."""
    return {
        "statement": "Qual é o resultado de 2 + 2?",
        "alternative_a": "3",
        "alternative_b": "4",
        "alternative_c": "5",
        "alternative_d": "6",
        "alternative_e": "7",
        "correct_answer": "B",
        "explanation": "2 + 2 = 4. Soma simples.",
        "difficulty": 1,
        "topic": "Aritmética",
    }


def _make_structured_response(questions: list[dict]) -> MagicMock:
    """Cria StructuredChatResponse simulado."""
    resp = MagicMock()
    resp.data = {"questions": questions}
    resp.model = "openai/gpt-4o-mini"
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = 50
    resp.usage.completion_tokens = 200
    resp.usage.total_tokens = 250
    resp.latency_ms = 500.0
    return resp


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


def _generator_config(**kwargs) -> QuestionGeneratorConfig:
    """Config do gerador para testes."""
    defaults = dict(max_per_request=5, max_per_hour=20, cache_ttl_seconds=3600)
    defaults.update(kwargs)
    return QuestionGeneratorConfig(**defaults)


def _make_generator(client=None, gen_config=None):
    """Cria QuestionGenerator com mocks."""
    if client is None:
        config = _enabled_config()
        tracker = UsageTracker()
        client = AIClient(config, tracker)
    return QuestionGenerator(client, gen_config)


# ---------------------------------------------------------------------------
# Testes: Prompts
# ---------------------------------------------------------------------------

class TestPrompts:
    """Testes para módulo de prompts."""

    def test_build_question_generation_prompt(self):
        """Prompt deve ter system e user messages."""
        messages = build_question_generation_prompt(
            area="matematica",
            materia="Matemática",
            assunto="Equações do 2º grau",
            dificuldade=3,
            quantidade=3,
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_prompt_contem_contexto(self):
        """Prompt deve conter contexto da questão."""
        messages = build_question_generation_prompt(
            area="humanas",
            materia="História",
            assunto="Brasil Colonial",
            dificuldade=2,
            quantidade=1,
        )
        user_content = messages[1]["content"]
        assert "humanas" in user_content
        assert "História" in user_content
        assert "Brasil Colonial" in user_content
        assert "2/5" in user_content

    def test_prompt_contem_quantidade(self):
        """Prompt deve especificar quantidade de questões."""
        messages = build_question_generation_prompt(
            area="natureza",
            materia="Química",
            assunto="Tabela Periódica",
            dificuldade=4,
            quantidade=5,
        )
        system_content = messages[0]["content"]
        assert "5" in system_content

    def test_prompt_contem_schema(self):
        """Prompt deve conter instruções de schema."""
        messages = build_question_generation_prompt(
            area="linguagens",
            materia="Português",
            assunto="Interpretação de texto",
            dificuldade=3,
            quantidade=1,
        )
        system_content = messages[0]["content"]
        assert "statement" in system_content
        assert "correct_answer" in system_content

    def test_build_single_question_prompt(self):
        """Atalho para uma questão deve funcionar."""
        messages = build_single_question_prompt(
            area="matematica",
            materia="Matemática",
            assunto="Geometria",
            dificuldade=3,
        )
        assert len(messages) == 2
        user_content = messages[1]["content"]
        assert "1" in user_content

    def test_prompt_dificuldade_labels(self):
        """Label de dificuldade deve variar."""
        for diff, label in [(1, "fácil"), (3, "médio"), (5, "difícil")]:
            messages = build_question_generation_prompt(
                area="a", materia="b", assunto="c",
                dificuldade=diff, quantidade=1,
            )
            assert label in messages[1]["content"]

    def test_prompt_version(self):
        """PROMPT_VERSION deve ser string."""
        assert isinstance(PROMPT_VERSION, str)
        assert len(PROMPT_VERSION) > 0


# ---------------------------------------------------------------------------
# Testes: Validators
# ---------------------------------------------------------------------------

class TestValidators:
    """Testes para validadores de questões."""

    def test_valid_question_passes(self):
        """Questão válida deve passar na validação."""
        result = validate_question(_valid_question_data())
        assert result.is_valid is True
        assert result.errors == []
        assert bool(result) is True

    def test_missing_required_fields(self):
        """Campos obrigatórios ausentes devem falhar."""
        result = validate_question({})
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_missing_statement(self):
        """Enunciado ausente deve falhar."""
        data = _valid_question_data()
        del data["statement"]
        result = validate_question(data)
        assert result.is_valid is False
        assert any("statement" in e for e in result.errors)

    def test_empty_statement(self):
        """Enunciado vazio deve falhar."""
        data = _valid_question_data()
        data["statement"] = ""
        result = validate_question(data)
        assert result.is_valid is False
        assert any("vazio" in e.lower() for e in result.errors)

    def test_statement_too_long(self):
        """Enunciado excessivamente longo deve falhar."""
        data = _valid_question_data()
        data["statement"] = "x" * 5001
        result = validate_question(data)
        assert result.is_valid is False
        assert any("5000" in e for e in result.errors)

    def test_missing_alternative(self):
        """Alternativa ausente deve falhar."""
        data = _valid_question_data()
        del data["alternative_c"]
        result = validate_question(data)
        assert result.is_valid is False

    def test_empty_alternative(self):
        """Alternativa vazia deve falhar."""
        data = _valid_question_data()
        data["alternative_b"] = ""
        result = validate_question(data)
        assert result.is_valid is False

    def test_alternative_too_long(self):
        """Alternativa excessivamente longa deve falhar."""
        data = _valid_question_data()
        data["alternative_a"] = "x" * 501
        result = validate_question(data)
        assert result.is_valid is False

    def test_invalid_correct_answer(self):
        """Gabarito inválido deve falhar."""
        data = _valid_question_data()
        data["correct_answer"] = "F"
        result = validate_question(data)
        assert result.is_valid is False
        assert any("inválida" in e.lower() for e in result.errors)

    def test_correct_answer_lowercase(self):
        """Gabarito minúsculo deve ser aceito (normalizado)."""
        data = _valid_question_data()
        data["correct_answer"] = "b"
        result = validate_question(data)
        assert result.is_valid is True

    def test_difficulty_out_of_range(self):
        """Dificuldade fora de 1-5 deve falhar."""
        data = _valid_question_data()
        data["difficulty"] = 6
        result = validate_question(data)
        assert result.is_valid is False
        assert any("fora do intervalo" in e for e in result.errors)

    def test_difficulty_zero(self):
        """Dificuldade 0 deve falhar."""
        data = _valid_question_data()
        data["difficulty"] = 0
        result = validate_question(data)
        assert result.is_valid is False

    def test_difficulty_invalid_type(self):
        """Dificuldade não numérica deve falhar."""
        data = _valid_question_data()
        data["difficulty"] = "abc"
        result = validate_question(data)
        assert result.is_valid is False

    def test_empty_topic(self):
        """Tópico vazio deve falhar."""
        data = _valid_question_data()
        data["topic"] = ""
        result = validate_question(data)
        assert result.is_valid is False

    def test_empty_explanation(self):
        """Explicação vazia deve falhar."""
        data = _valid_question_data()
        data["explanation"] = ""
        result = validate_question(data)
        assert result.is_valid is False

    def test_explanation_too_long(self):
        """Explicação excessivamente longa deve falhar."""
        data = _valid_question_data()
        data["explanation"] = "x" * 2001
        result = validate_question(data)
        assert result.is_valid is False

    def test_duplicate_alternatives(self):
        """Alternativas duplicadas devem falhar."""
        data = _valid_question_data()
        data["alternative_a"] = "resposta igual"
        data["alternative_c"] = "resposta igual"
        result = validate_question(data)
        assert result.is_valid is False
        assert any("duplicad" in e.lower() for e in result.errors)

    def test_duplicate_alternatives_case_insensitive(self):
        """Duplicatas devem ser detectadas case-insensitive."""
        data = _valid_question_data()
        data["alternative_a"] = "Resposta"
        data["alternative_d"] = "resposta"
        result = validate_question(data)
        assert result.is_valid is False

    def test_validate_question_batch(self):
        """Lote deve validar todas as questões."""
        valid = _valid_question_data()
        invalid = _valid_question_data()
        del invalid["statement"]
        results = validate_question_batch([valid, invalid])
        assert len(results) == 2
        assert results[0].is_valid is True
        assert results[1].is_valid is False

    def test_validate_question_batch_empty(self):
        """Lote vazio deve retornar lista vazia."""
        results = validate_question_batch([])
        assert results == []


class TestSanitizeQuestion:
    """Testes para sanitize_question."""

    def test_strip_whitespace(self):
        """Deve remover espaços extras."""
        data = _valid_question_data()
        data["statement"] = "  Questão com   espaços  "
        sanitized = sanitize_question(data)
        assert sanitized["statement"] == "Questão com espaços"

    def test_uppercase_answer(self):
        """Gabarito deve ser maiúsculo."""
        data = _valid_question_data()
        data["correct_answer"] = "b"
        sanitized = sanitize_question(data)
        assert sanitized["correct_answer"] == "B"

    def test_difficulty_as_int(self):
        """Dificuldade deve ser convertida para int."""
        data = _valid_question_data()
        data["difficulty"] = "3"
        sanitized = sanitize_question(data)
        assert sanitized["difficulty"] == 3

    def test_difficulty_invalid_default(self):
        """Dificuldade inválida deve virar 3."""
        data = _valid_question_data()
        data["difficulty"] = "abc"
        sanitized = sanitize_question(data)
        assert sanitized["difficulty"] == 3

    def test_sanitize_preserves_structure(self):
        """Sanitize não deve remover chaves válidas."""
        data = _valid_question_data()
        sanitized = sanitize_question(data)
        assert set(data.keys()) == set(sanitized.keys())


# ---------------------------------------------------------------------------
# Testes: QuestionGeneratorConfig
# ---------------------------------------------------------------------------

class TestQuestionGeneratorConfig:
    """Testes para configuração do gerador."""

    def test_default_config(self):
        """Config padrão deve ter valores razoáveis."""
        config = QuestionGeneratorConfig()
        assert config.max_per_request == 5
        assert config.max_per_hour == 20
        assert config.cache_ttl_seconds == 3600

    def test_custom_config(self):
        """Config customizada deve ser aceita."""
        config = QuestionGeneratorConfig(max_per_request=3, max_per_hour=10)
        assert config.max_per_request == 3
        assert config.max_per_hour == 10


# ---------------------------------------------------------------------------
# Testes: GeneratedQuestion
# ---------------------------------------------------------------------------

class TestGeneratedQuestion:
    """Testes para GeneratedQuestion."""

    def test_created_successfully(self):
        """Deve criar GeneratedQuestion com todos os campos."""
        q = GeneratedQuestion(
            statement="Teste",
            alternative_a="A", alternative_b="B", alternative_c="C",
            alternative_d="D", alternative_e="E",
            correct_answer="A",
            explanation="Explicação",
            difficulty=3,
            topic="Tópico",
        )
        assert q.statement == "Teste"
        assert q.correct_answer == "A"
        assert q.validation_status == "pending"

    def test_to_db_dict(self):
        """to_db_dict() deve serializar corretamente para o banco."""
        q = GeneratedQuestion(
            statement="Enunciado",
            alternative_a="A", alternative_b="B", alternative_c="C",
            alternative_d="D", alternative_e="E",
            correct_answer="C",
            explanation="Explicação",
            difficulty=2,
            topic="Tópico",
            model="gpt-4o-mini",
            prompt_version="1.0",
        )
        d = q.to_db_dict()
        assert d["enunciado"] == "Enunciado"
        assert d["alternativa_a"] == "A"
        assert d["resposta_correta"] == "C"
        assert d["dificuldade"] == 2
        assert "gpt-4o-mini" in d["fonte"]

    def test_default_validation_status(self):
        """Status padrão deve ser 'pending'."""
        q = GeneratedQuestion(
            statement="T", alternative_a="A", alternative_b="B",
            alternative_c="C", alternative_d="D", alternative_e="E",
            correct_answer="A", explanation="E", difficulty=3, topic="T",
        )
        assert q.validation_status == "pending"


# ---------------------------------------------------------------------------
# Testes: QuestionGenerator
# ---------------------------------------------------------------------------

class TestQuestionGenerator:
    """Testes para QuestionGenerator."""

    def test_repr(self):
        """repr não deve expor dados sensíveis."""
        gen = _make_generator()
        r = repr(gen)
        assert "QuestionGenerator" in r
        assert "max_per_request" in r

    def test_client_must_be_enabled(self):
        """Generator com client desabilitado deve levantar AIDisabledError."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client)
        with pytest.raises(AIDisabledError):
            gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

    def test_generate_sucesso(self):
        """Geração válida deve retornar questões validadas."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "matematica", "Matemática", "Equações", 3, 1)

        assert len(results) == 1
        assert results[0].statement == "Qual é o resultado de 2 + 2?"
        assert results[0].correct_answer == "B"
        assert results[0].validation_status == "approved"

    def test_generate_lote(self):
        """Geração em lote deve retornar múltiplas questões."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        questions = [_valid_question_data() for _ in range(3)]
        mock_structured = _make_structured_response(questions)

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "mat", "Mat", "Eq", 3, 3)

        assert len(results) == 3

    def test_generate_respects_max_per_request(self):
        """Deve respeitar limite de max_per_request."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(
            client,
            _generator_config(max_per_request=2, cache_ttl_seconds=0),
        )

        questions = [_valid_question_data() for _ in range(5)]
        mock_structured = _make_structured_response(questions)

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "mat", "Mat", "Eq", 3, 10)

        assert len(results) <= 2

    def test_generate_invalid_question_filtered(self):
        """Questões inválidas devem ser filtradas."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        valid = _valid_question_data()
        invalid = _valid_question_data()
        invalid["correct_answer"] = "Z"

        mock_structured = _make_structured_response([valid, invalid])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "mat", "Mat", "Eq", 3, 2)

        assert len(results) == 1

    def test_generate_all_invalid_returns_empty(self):
        """Se todas forem inválidas, retorna lista vazia."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        invalid = _valid_question_data()
        invalid["correct_answer"] = "Z"
        invalid["statement"] = ""

        mock_structured = _make_structured_response([invalid])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

        assert results == []

    def test_generate_ai_response_not_list(self):
        """Resposta da IA sem lista 'questions' deve levantar erro."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        mock_structured = MagicMock()
        mock_structured.data = {"questions": "not a list"}
        mock_structured.model = "test"

        with patch.object(client, "chat_structured", return_value=mock_structured):
            with pytest.raises(AIValidationError):
                gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

    def test_generate_single(self):
        """generate_single deve retornar uma questão ou None."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            result = gen.generate_single("user1", "mat", "Mat", "Eq", 3)

        assert result is not None
        assert result.statement == "Qual é o resultado de 2 + 2?"

    def test_generate_single_none_on_invalid(self):
        """generate_single deve retornar None se inválida."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        invalid = _valid_question_data()
        invalid["correct_answer"] = "Z"
        mock_structured = _make_structured_response([invalid])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            result = gen.generate_single("user1", "mat", "Mat", "Eq", 3)

        assert result is None

    def test_generate_sanitizes_output(self):
        """Saída deve ser sanitizada antes de criar GeneratedQuestion."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        dirty = _valid_question_data()
        dirty["correct_answer"] = "b"
        dirty["statement"] = "  Questão suja  "

        mock_structured = _make_structured_response([dirty])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

        assert results[0].correct_answer == "B"
        assert results[0].statement == "Questão suja"

    def test_generate_recorded_model(self):
        """Modelo deve ser registrado na questão."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

        assert results[0].model == "openai/gpt-4o-mini"


# ---------------------------------------------------------------------------
# Testes: Cache
# ---------------------------------------------------------------------------

class TestCache:
    """Testes para cache de questões."""

    def test_cache_hit(self):
        """Segunda chamada com mesmos parâmetros deve usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=60))

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured) as mock_cs:
            results1 = gen.generate("user1", "mat", "Mat", "Eq", 3, 1)
            results2 = gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

        assert mock_cs.call_count == 1
        assert len(results1) == 1
        assert len(results2) == 1

    def test_cache_different_params(self):
        """Parâmetros diferentes não devem usar cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=60))

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured) as mock_cs:
            gen.generate("user1", "mat", "Mat", "Eq1", 3, 1)
            gen.generate("user1", "mat", "Mat", "Eq2", 3, 1)

        assert mock_cs.call_count == 2

    def test_cache_expiry(self):
        """Cache deve expirar após TTL."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured) as mock_cs:
            gen.generate("user1", "mat", "Mat", "Eq", 3, 1)
            gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

        assert mock_cs.call_count == 2

    def test_clear_cache(self):
        """clear_cache() deve limpar o cache."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=60))

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        mock_method = MagicMock(return_value=mock_structured)

        with patch.object(client, "chat_structured", side_effect=mock_method):
            gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

        gen.clear_cache()

        with patch.object(client, "chat_structured", side_effect=mock_method):
            gen.generate("user1", "mat", "Mat", "Eq", 3, 1)

        assert mock_method.call_count == 2

    def test_get_cached(self):
        """get_cached() deve retornar cache válido."""
        gen = _make_generator()
        gen._config = QuestionGeneratorConfig(cache_ttl_seconds=60)

        q = GeneratedQuestion(
            statement="T", alternative_a="A", alternative_b="B",
            alternative_c="C", alternative_d="D", alternative_e="E",
            correct_answer="A", explanation="E", difficulty=3, topic="T",
        )
        key = gen._cache_key("mat", "Mat", "Eq", 3)
        gen._cache[key] = _CacheEntry(questions=[q], created_at=time.monotonic())

        cached = gen.get_cached("mat", "Mat", "Eq", 3)
        assert len(cached) == 1

    def test_get_cached_expired(self):
        """get_cached() deve retornar vazio se expirado."""
        gen = _make_generator()
        gen._config = QuestionGeneratorConfig(cache_ttl_seconds=0)

        q = GeneratedQuestion(
            statement="T", alternative_a="A", alternative_b="B",
            alternative_c="C", alternative_d="D", alternative_e="E",
            correct_answer="A", explanation="E", difficulty=3, topic="T",
        )
        key = gen._cache_key("mat", "Mat", "Eq", 3)
        gen._cache[key] = _CacheEntry(questions=[q], created_at=time.monotonic() - 10)

        cached = gen.get_cached("mat", "Mat", "Eq", 3)
        assert cached == []


# ---------------------------------------------------------------------------
# Testes: Limites
# ---------------------------------------------------------------------------

class TestRateLimits:
    """Testes para limites de taxa."""

    def test_hourly_limit_reached(self):
        """Deve levantar ValueError ao atingir limite horário."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(
            client,
            _generator_config(max_per_hour=2, cache_ttl_seconds=0),
        )

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            gen.generate("user1", "a", "b", "c", 3, 1)
            gen.generate("user1", "a2", "b", "c", 3, 1)

        with pytest.raises(ValueError, match="Limite horário"):
            gen.generate("user1", "a3", "b", "c", 3, 1)

    def test_different_users_independent(self):
        """Limite deve ser por usuário."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(
            client,
            _generator_config(max_per_hour=1, cache_ttl_seconds=0),
        )

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            gen.generate("user1", "a", "b", "c", 3, 1)
            gen.generate("user2", "a2", "b", "c", 3, 1)

    def test_remaining_hourly(self):
        """remaining_hourly() deve retornar quantas questões restam."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(
            client,
            _generator_config(max_per_hour=3, cache_ttl_seconds=0),
        )

        assert gen.remaining_hourly("user1") == 3

        question_data = _valid_question_data()
        mock_structured = _make_structured_response([question_data])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            gen.generate("user1", "a", "b", "c", 3, 1)

        assert gen.remaining_hourly("user1") == 2

    def test_max_per_request_clamp(self):
        """Quantidade deve ser limitada por max_per_request."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(
            client,
            _generator_config(max_per_request=2, max_per_hour=100, cache_ttl_seconds=0),
        )

        questions = [_valid_question_data() for _ in range(5)]
        mock_structured = _make_structured_response(questions)

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "a", "b", "c", 3, 100)

        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Testes: Provider Offline
# ---------------------------------------------------------------------------

class TestProviderOffline:
    """Testes para cenários de provider indisponível."""

    def test_ai_disabled_error_propagates(self):
        """AIDisabledError deve ser propagada corretamente."""
        config = AIConfig(enabled=False)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client)

        with pytest.raises(AIDisabledError):
            gen.generate("user1", "a", "b", "c", 3, 1)

    def test_provider_error_propagates(self):
        """AIProviderError deve ser propagada."""
        from app.ai.exceptions import AIProviderError

        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        with patch.object(
            client, "chat_structured", side_effect=AIProviderError("Provider offline")
        ):
            with pytest.raises(AIProviderError):
                gen.generate("user1", "a", "b", "c", 3, 1)


# ---------------------------------------------------------------------------
# Testes: Response Size
# ---------------------------------------------------------------------------

class TestResponseSize:
    """Testes para respostas excessivamente grandes."""

    def test_statement_truncation_not_needed(self):
        """Enunciado longo mas dentro do limite deve ser aceito."""
        data = _valid_question_data()
        data["statement"] = "x" * 4999
        result = validate_question(data)
        assert result.is_valid is True

    def test_alternative_at_limit(self):
        """Alternativa no limite exato deve ser aceita."""
        data = _valid_question_data()
        data["alternative_a"] = "x" * 500
        result = validate_question(data)
        assert result.is_valid is True

    def test_explanation_at_limit(self):
        """Explicação no limite exato deve ser aceita."""
        data = _valid_question_data()
        data["explanation"] = "x" * 2000
        result = validate_question(data)
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# Testes: Integração AIClient + Generator
# ---------------------------------------------------------------------------

class TestIntegrationAIClientGenerator:
    """Testes de integração entre AIClient e QuestionGenerator."""

    def test_full_flow(self):
        """Fluxo completo: generator -> client -> validação."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        questions = [
            _valid_question_data(),
            _valid_question_data(),
        ]
        mock_structured = _make_structured_response(questions)

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "matematica", "Mat", "Álgebra", 2, 2)

        assert len(results) == 2
        for q in results:
            assert q.validation_status == "approved"
            assert q.model == "openai/gpt-4o-mini"
            assert q.prompt_version == PROMPT_VERSION

    def test_to_db_dict_ready(self):
        """to_db_dict() deve ser compatível com Question model."""
        config = _enabled_config(max_retries=0)
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        gen = QuestionGenerator(client, _generator_config(cache_ttl_seconds=0))

        mock_structured = _make_structured_response([_valid_question_data()])

        with patch.object(client, "chat_structured", return_value=mock_structured):
            results = gen.generate("user1", "m", "M", "A", 3, 1)

        db_dict = results[0].to_db_dict()
        assert "enunciado" in db_dict
        assert "alternativa_a" in db_dict
        assert "resposta_correta" in db_dict
        assert "dificuldade" in db_dict
        assert "fonte" in db_dict


# ---------------------------------------------------------------------------
# Testes: AIConfig extensões
# ---------------------------------------------------------------------------

class TestAIConfigExtensions:
    """Testes para novos campos de config."""

    def test_max_questions_defaults(self):
        """Defaults de max_questions devem existir."""
        config = AIConfig()
        assert config.max_questions_per_request == 5
        assert config.max_questions_per_hour == 20

    def test_custom_limits(self):
        """Limites customizados devem funcionar."""
        config = AIConfig(
            enabled=True, api_key="k", model="m",
            max_questions_per_request=3,
            max_questions_per_hour=10,
        )
        assert config.max_questions_per_request == 3
        assert config.max_questions_per_hour == 10


from app.ai.question_generator import _CacheEntry
