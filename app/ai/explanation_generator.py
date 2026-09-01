"""
Gerador de explicações por IA - PlanejaENEM 5.0.

Gera explicações personalizadas para questões respondidas pelo aluno.
Explica por que o aluno errou e como chegar à resposta correta.

REGRA DE OURO: A IA APENAS explica.
Nunca altera números, calcula mastery, modifica tendência ou decide planejamento.
O backend fornece os dados verdadeiros; a IA apenas personaliza a explicação.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import time
from dataclasses import dataclass, field

from app.ai.client import AIClient
from app.ai.exceptions import AIError, AIDisabledError, AIValidationError
from app.ai.prompts import PROMPT_VERSION
from app.ai.schemas import ChatRequest, Message

logger = logging.getLogger(__name__)

_MAX_EXPLANATION_LENGTH = 2000
_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class ExplanationInput:
    """Dados de entrada para geração de explicação."""

    question_id: str
    statement: str
    alternatives: dict[str, str]
    student_answer: str
    correct_answer: str
    materia: str
    assunto: str
    dificuldade: int
    mastery: float | None = None
    trend: str | None = None
    recurring_error: str | None = None


@dataclass(frozen=True)
class ExplanationOutput:
    """Saída estruturada da explicação."""

    summary: str
    concept: str
    steps: list[str]
    common_mistake: str
    study_tip: str


@dataclass
class _CacheEntry:
    """Entrada de cache com timestamp."""

    output: ExplanationOutput
    created_at: float


def _sanitize_text(text: str) -> str:
    """Remove HTML perigoso e normaliza whitespace."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_EXPLANATION_LENGTH]


def _build_explanation_prompt(inp: ExplanationInput) -> list[dict]:
    """Constrói mensagens para geração de explicação."""
    alt_text = "\n".join(
        f"  {letter}: {text}" for letter, text in sorted(inp.alternatives.items())
    )

    context_lines = [
        f"- Matéria: {inp.materia}",
        f"- Assunto: {inp.assunto}",
        f"- Dificuldade: {inp.dificuldade}/5",
    ]
    if inp.mastery is not None:
        context_lines.append(f"- Mastery do aluno: {inp.mastery:.0%}")
    if inp.trend:
        context_lines.append(f"- Tendência: {inp.trend}")
    if inp.recurring_error:
        context_lines.append(f"- Erro recorrente: {inp.recurring_error}")

    context = "\n".join(context_lines)

    system_msg = (
        "Você é um tutor educativo do ENEM. "
        "Explique de forma clara e didática.\n\n"
        "REGRAS:\n"
        "- Seja conciso (máx. 3 parágrafos).\n"
        "- Use linguagem acessível para estudantes do ensino médio.\n"
        "- NÃO invente dados estatísticos.\n"
        "- NÃO altere a resposta correta.\n"
        "- Foque no conceito, não na decoreba.\n\n"
        "Responda APENAS com JSON válido (sem markdown, sem ```).\n"
        "Schema obrigatório:\n"
        "{\n"
        '  "summary": "resumo da explicação em 1-2 frases",\n'
        '  "concept": "conceito fundamental abordado pela questão",\n'
        '  "steps": ["passo 1", "passo 2", "passo 3"],\n'
        '  "common_mistake": "erro comum que o aluno cometeu",\n'
        '  "study_tip": "dica prática de estudo"\n'
        "}"
    )

    is_correct = inp.student_answer.upper() == inp.correct_answer.upper()

    if is_correct:
        user_msg = (
            f"O aluno ACERTOU esta questão. Explique por que a resposta está correta "
            f"e reforce o conceito.\n\n"
            f"Contexto:\n{context}\n\n"
            f"Enunciado:\n{inp.statement}\n\n"
            f"Alternativas:\n{alt_text}\n\n"
            f"Resposta correta: {inp.correct_answer}\n"
            f"Resposta do aluno: {inp.student_answer} (correta)\n\n"
            f"Retorne APENAS o JSON no schema especificado."
        )
    else:
        user_msg = (
            f"O aluno ERROU esta questão. Explique o erro e mostre o caminho correto.\n\n"
            f"Contexto:\n{context}\n\n"
            f"Enunciado:\n{inp.statement}\n\n"
            f"Alternativas:\n{alt_text}\n\n"
            f"Resposta correta: {inp.correct_answer}\n"
            f"Resposta do aluno: {inp.student_answer} (incorreta)\n\n"
            f"Retorne APENAS o JSON no schema especificado."
        )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _parse_explanation(data: dict) -> ExplanationOutput:
    """Parse e validação da resposta da IA."""
    steps = data.get("steps", [])
    if not isinstance(steps, list):
        steps = [str(steps)]
    steps = [_sanitize_text(str(s)) for s in steps if str(s).strip()]
    steps = [s for s in steps if s]

    return ExplanationOutput(
        summary=_sanitize_text(str(data.get("summary", ""))),
        concept=_sanitize_text(str(data.get("concept", ""))),
        steps=steps[:10],
        common_mistake=_sanitize_text(str(data.get("common_mistake", ""))),
        study_tip=_sanitize_text(str(data.get("study_tip", ""))),
    )


def _fallback_explanation(inp: ExplanationInput) -> ExplanationOutput:
    """Explicação de fallback quando a IA falha."""
    is_correct = inp.student_answer.upper() == inp.correct_answer.upper()

    if is_correct:
        return ExplanationOutput(
            summary=f"Você acertou! A resposta correta é {inp.correct_answer}.",
            concept=f"Conceito: {inp.assunto} ({inp.materia}).",
            steps=[f"Releia o enunciado com atenção.", f"Revise o tópico: {inp.assunto}."],
            common_mistake="",
            study_tip=f"Continue praticando {inp.assunto} para manter seu desempenho.",
        )

    return ExplanationOutput(
        summary=(
            f"Você errou. A resposta correta é {inp.correct_answer}, "
            f"mas você marcou {inp.student_answer}."
        ),
        concept=f"Conceito: {inp.assunto} ({inp.materia}).",
        steps=[
            f"Revise o tópico: {inp.assunto}.",
            f"Leia com atenção cada alternativa antes de responder.",
        ],
        common_mistake=f"Confusão entre as alternativas em {inp.assunto}.",
        study_tip=f"Pratique mais questões de {inp.assunto} para fixar o conteúdo.",
    )


class ExplanationGenerator:
    """
    Gerador de explicações usando IA generativa.

    Usa AIClient exclusivamente. Nunca faz chamadas HTTP diretas.
    Implementa cache, sanitização e fallback.

    REGRA DE OURO: A IA apenas explica.
    O backend fornece accuracy, mastery, confidence, trend.
    """

    def __init__(
        self,
        client: AIClient,
        cache_ttl: int = _CACHE_TTL_SECONDS,
        max_tokens: int = 800,
    ) -> None:
        self._client = client
        self._cache_ttl = cache_ttl
        self._max_tokens = max_tokens
        self._cache: dict[str, _CacheEntry] = {}

    def _cache_key(self, inp: ExplanationInput) -> str:
        """Gera chave de cache baseada no conteúdo da questão."""
        raw = (
            f"{inp.question_id}|{inp.student_answer}|{inp.correct_answer}|"
            f"{PROMPT_VERSION}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _is_cache_valid(self, key: str) -> bool:
        """Verifica se entrada de cache ainda é válida."""
        entry = self._cache.get(key)
        if not entry:
            return False
        elapsed = time.monotonic() - entry.created_at
        return elapsed < self._cache_ttl

    def generate(self, inp: ExplanationInput) -> ExplanationOutput:
        """
        Gera explicação para uma questão.

        Args:
            inp: Dados da questão e resposta do aluno.

        Returns:
            ExplanationOutput com explicação estruturada.
        """
        if not self._client.enabled:
            logger.warning("IA desligada, usando fallback para explicação")
            return _fallback_explanation(inp)

        cache_key = self._cache_key(inp)
        if self._is_cache_valid(cache_key):
            logger.info("Cache hit para explicação: %s", inp.question_id)
            return self._cache[cache_key].output

        messages = _build_explanation_prompt(inp)
        chat_messages = [Message(role=m["role"], content=m["content"]) for m in messages]
        request = ChatRequest(
            messages=chat_messages,
            temperature=0.3,
            max_tokens=self._max_tokens,
        )

        try:
            structured = self._client.chat_structured(
                request,
                expected_keys=["summary", "concept", "steps", "common_mistake", "study_tip"],
                feature="explanation",
            )
            output = _parse_explanation(structured.data)
        except (AIError, AIValidationError, Exception) as exc:
            logger.warning(
                "Erro ao gerar explicação para %s: %s. Usando fallback.",
                inp.question_id,
                exc,
            )
            return _fallback_explanation(inp)

        self._cache[cache_key] = _CacheEntry(
            output=output,
            created_at=time.monotonic(),
        )

        return output

    def get_cached(self, inp: ExplanationInput) -> ExplanationOutput | None:
        """Retorna explicação em cache (se válida)."""
        key = self._cache_key(inp)
        if self._is_cache_valid(key):
            return self._cache[key].output
        return None

    def clear_cache(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()

    def __repr__(self) -> str:
        return (
            f"ExplanationGenerator(cache_ttl={self._cache_ttl}, "
            f"max_tokens={self._max_tokens})"
        )
