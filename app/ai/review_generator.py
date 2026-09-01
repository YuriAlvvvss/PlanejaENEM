"""
Gerador de revisões personalizadas por IA - PlanejaENEM 5.0.

Gera revisões curtas e focadas para assuntos prioritários
identificados pelo Decision Engine.

REGRA DE OURO: A IA APENAS gera a revisão solicitada.
Nunca altera mastery, score, prioridade, tendência ou planejamento.
O backend fornece os dados verdadeiros; a IA personaliza a apresentação.
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
from app.ai.exceptions import AIError, AIValidationError
from app.ai.prompts import PROMPT_VERSION
from app.ai.schemas import ChatRequest, Message

logger = logging.getLogger(__name__)

_MAX_REVIEW_LENGTH = 3000
_CACHE_TTL_SECONDS = 3600

_DURATION_CONFIGS = {
    5: {"max_tokens": 600, "label": "rápida"},
    10: {"max_tokens": 1000, "label": "curta"},
    20: {"max_tokens": 1500, "label": "completa"},
}


@dataclass(frozen=True)
class ReviewInput:
    """Dados de entrada para geração de revisão."""

    materia: str
    assunto: str
    mastery: float
    confidence: float
    weak_concepts: list[str]
    recent_errors: list[str]
    duration_minutes: int = 10


@dataclass(frozen=True)
class ReviewOutput:
    """Saída estruturada da revisão."""

    title: str
    summary: str
    key_concepts: list[str]
    worked_example: str
    common_mistakes: list[str]
    quick_check: str


@dataclass
class _CacheEntry:
    """Entrada de cache com timestamp."""

    output: ReviewOutput
    created_at: float


def _sanitize_text(text: str) -> str:
    """Remove HTML perigoso e normaliza whitespace."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_REVIEW_LENGTH]


def _validate_duration(duration: int) -> int:
    """Valida e normaliza a duração (5, 10 ou 20 min)."""
    if duration not in _DURATION_CONFIGS:
        if duration <= 5:
            return 5
        elif duration <= 10:
            return 10
        else:
            return 20
    return duration


def _build_review_prompt(inp: ReviewInput) -> list[dict]:
    """Constrói mensagens para geração de revisão."""
    duration = _validate_duration(inp.duration_minutes)
    config = _DURATION_CONFIGS[duration]

    weak_concepts_text = (
        ", ".join(inp.weak_concepts) if inp.weak_concepts else "Nenhum específico"
    )
    recent_errors_text = (
        "\n".join(f"- {e}" for e in inp.recent_errors[:5])
        if inp.recent_errors
        else "Nenhum erro recente registrado"
    )

    system_msg = (
        "Você é um tutor educativo do ENEM. "
        f"Gere uma revisão {config['label']} sobre o tema.\n\n"
        "REGRAS:\n"
        "- Seja conciso e direto ao ponto.\n"
        "- Use linguagem acessível para estudantes do ensino médio.\n"
        "- Foque nos conceitos fracos identificados.\n"
        "- NÃO invente dados estatísticos.\n"
        "- NÃO altere mastery, score ou tendência.\n"
        "- O conteúdo deve ser factual e verificável.\n\n"
        f"DURAÇÃO: {duration} minutos\n"
        f"- {'Resumo e exemplo worked' if duration == 5 else ''}\n"
        f"- {'Resumo, exemplo worked e mini-exercício' if duration == 10 else ''}\n"
        f"- {'Revisão completa, exemplos e exercícios' if duration == 20 else ''}\n\n"
        "Responda APENAS com JSON válido (sem markdown, sem ```).\n"
        "Schema obrigatório:\n"
        "{\n"
        '  "title": "título da revisão",\n'
        '  "summary": "resumo conciso do assunto",\n'
        '  "key_concepts": ["conceito 1", "conceito 2", "conceito 3"],\n'
        '  "worked_example": "exemplo resolvido passo a passo",\n'
        '  "common_mistakes": ["erro comum 1", "erro comum 2"],\n'
        '  "quick_check": "pergunta rápida de autoavaliação"\n'
        "}"
    )

    user_msg = (
        f"Gere uma revisão personalizada:\n\n"
        f"Matéria: {inp.materia}\n"
        f"Assunto: {inp.assunto}\n"
        f"Mastery atual: {inp.mastery:.0%}\n"
        f"Confiança: {inp.confidence:.0%}\n"
        f"Conceitos fracos: {weak_concepts_text}\n"
        f"Erros recentes:\n{recent_errors_text}\n\n"
        f"Retorne APENAS o JSON no schema especificado."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _parse_review(data: dict) -> ReviewOutput:
    """Parse e validação da resposta da IA."""
    key_concepts = data.get("key_concepts", [])
    if not isinstance(key_concepts, list):
        key_concepts = [str(key_concepts)]
    key_concepts = [_sanitize_text(str(k)) for k in key_concepts if str(k).strip()]

    common_mistakes = data.get("common_mistakes", [])
    if not isinstance(common_mistakes, list):
        common_mistakes = [str(common_mistakes)]
    common_mistakes = [_sanitize_text(str(m)) for m in common_mistakes if str(m).strip()]

    return ReviewOutput(
        title=_sanitize_text(str(data.get("title", ""))),
        summary=_sanitize_text(str(data.get("summary", ""))),
        key_concepts=key_concepts[:5],
        worked_example=_sanitize_text(str(data.get("worked_example", ""))),
        common_mistakes=common_mistakes[:3],
        quick_check=_sanitize_text(str(data.get("quick_check", ""))),
    )


def _fallback_review(inp: ReviewInput) -> ReviewOutput:
    """Revisão de fallback quando a IA falha."""
    duration = _validate_duration(inp.duration_minutes)

    weak_concepts = inp.weak_concepts[:3] if inp.weak_concepts else [inp.assunto]
    concepts_str = ", ".join(weak_concepts)

    summary_parts = [
        f"Revisão de {inp.assunto} ({inp.materia}).",
        f"Seu mastery atual é {inp.mastery:.0%}.",
    ]
    if inp.weak_concepts:
        summary_parts.append(f"Foque nos conceitos: {concepts_str}.")
    summary = " ".join(summary_parts)

    quick_check = (
        f"Resuma em 2-3 frases o que você aprendeu sobre {inp.assunto}."
    )
    if duration >= 10:
        quick_check += (
            f" Tente resolver um exemplo prático sobre {weak_concepts[0]}."
        )
    if duration >= 20:
        quick_check += (
            " Elabore uma questão de múltipla escolha sobre o tema."
        )

    return ReviewOutput(
        title=f"Revisão: {inp.assunto}",
        summary=summary,
        key_concepts=weak_concepts,
        worked_example=f"Exemplo: resolva uma questão sobre {weak_concepts[0]}.",
        common_mistakes=[
            f"Erro comum em {c}" for c in weak_concepts[:2]
        ] if weak_concepts else ["Confusão de conceitos básicos"],
        quick_check=quick_check,
    )


class ReviewGenerator:
    """
    Gerador de revisões personalizadas usando IA generativa.

    Usa AIClient exclusivamente. Nunca faz chamadas HTTP diretas.
    Implementa cache, sanitização e fallback.

    REGRA DE OURO: A IA apenas gera a revisão solicitada.
    O backend fornece mastery, confidence, conceitos fracos e erros recentes.
    """

    def __init__(
        self,
        client: AIClient,
        cache_ttl: int = _CACHE_TTL_SECONDS,
        default_max_tokens: int = 1000,
    ) -> None:
        self._client = client
        self._cache_ttl = cache_ttl
        self._default_max_tokens = default_max_tokens
        self._cache: dict[str, _CacheEntry] = {}

    def _cache_key(self, inp: ReviewInput) -> str:
        """Gera chave de cache baseada no tópico e dificuldade."""
        duration = _validate_duration(inp.duration_minutes)
        weak_str = "|".join(sorted(inp.weak_concepts))
        errors_str = "|".join(sorted(inp.recent_errors[:3]))
        raw = (
            f"{inp.materia}|{inp.assunto}|{inp.mastery:.4f}|"
            f"{inp.confidence:.4f}|{weak_str}|{errors_str}|"
            f"{duration}|{PROMPT_VERSION}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _is_cache_valid(self, key: str) -> bool:
        """Verifica se entrada de cache ainda é válida."""
        entry = self._cache.get(key)
        if not entry:
            return False
        elapsed = time.monotonic() - entry.created_at
        return elapsed < self._cache_ttl

    def generate(self, inp: ReviewInput) -> ReviewOutput:
        """
        Gera revisão personalizada para um assunto prioritário.

        Args:
            inp: Dados do assunto e contexto do aluno.

        Returns:
            ReviewOutput com revisão estruturada.
        """
        if not self._client.enabled:
            logger.warning("IA desligada, usando fallback para revisão")
            return _fallback_review(inp)

        cache_key = self._cache_key(inp)
        if self._is_cache_valid(cache_key):
            logger.info("Cache hit para revisão: %s", inp.assunto)
            return self._cache[cache_key].output

        duration = _validate_duration(inp.duration_minutes)
        config = _DURATION_CONFIGS.get(duration, _DURATION_CONFIGS[10])
        max_tokens = min(config.get("max_tokens", self._default_max_tokens), self._default_max_tokens)

        messages = _build_review_prompt(inp)
        chat_messages = [Message(role=m["role"], content=m["content"]) for m in messages]
        request = ChatRequest(
            messages=chat_messages,
            temperature=0.3,
            max_tokens=max_tokens,
        )

        try:
            structured = self._client.chat_structured(
                request,
                expected_keys=[
                    "title", "summary", "key_concepts",
                    "worked_example", "common_mistakes", "quick_check",
                ],
                feature="review",
            )
            output = _parse_review(structured.data)
        except (AIError, AIValidationError, Exception) as exc:
            logger.warning(
                "Erro ao gerar revisão para %s: %s. Usando fallback.",
                inp.assunto,
                exc,
            )
            return _fallback_review(inp)

        self._cache[cache_key] = _CacheEntry(
            output=output,
            created_at=time.monotonic(),
        )

        return output

    def get_cached(self, inp: ReviewInput) -> ReviewOutput | None:
        """Retorna revisão em cache (se válida)."""
        key = self._cache_key(inp)
        if self._is_cache_valid(key):
            return self._cache[key].output
        return None

    def clear_cache(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()

    def __repr__(self) -> str:
        return (
            f"ReviewGenerator(cache_ttl={self._cache_ttl}, "
            f"default_max_tokens={self._default_max_tokens})"
        )
