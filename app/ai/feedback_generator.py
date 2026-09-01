"""
Gerador de feedback por IA - PlanejaENEM 5.0.

Gera feedback personalizado sobre o desempenho do aluno.
Recebe dados estatísticos do backend (fonte da verdade)
e personaliza a apresentação com IA generativa.

REGRA DE OURO: A IA APENAS explica e personaliza.
Nunca altera números, calcula mastery, modifica tendência
ou decide planejamento. O backend fornece os dados verdadeiros.
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

_MAX_FEEDBACK_LENGTH = 3000
_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class PerformanceData:
    """Dados de desempenho recebidos do backend (fonte da verdade)."""

    accuracy: float
    mastery: float
    confidence: float
    trend: str
    strong_points: list[str]
    weak_points: list[str]
    recent_performance: list[float]
    historical_performance: list[float]


@dataclass(frozen=True)
class FeedbackOutput:
    """Saída estruturada do feedback."""

    summary: str
    strengths: list[str]
    weaknesses: list[str]
    advice: str
    next_step: str


@dataclass
class _CacheEntry:
    """Entrada de cache com timestamp."""

    output: FeedbackOutput
    created_at: float


def _sanitize_text(text: str) -> str:
    """Remove HTML perigoso e normaliza whitespace."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_FEEDBACK_LENGTH]


def _build_feedback_prompt(data: PerformanceData) -> list[dict]:
    """Constrói mensagens para geração de feedback."""
    strong = ", ".join(data.strong_points) if data.strong_points else "Nenhum identificado"
    weak = ", ".join(data.weak_points) if data.weak_points else "Nenhum identificado"

    recent_str = ", ".join(f"{p:.0%}" for p in data.recent_performance[-5:])
    historical_str = ", ".join(f"{p:.0%}" for p in data.historical_performance[-5:])

    system_msg = (
        "Você é um tutor educativo do ENEM. "
        "Forneça feedback motivacional e prático.\n\n"
        "REGRAS:\n"
        "- Seja positivo mas realista.\n"
        "- Foque em ações concretas.\n"
        "- NÃO invente dados ou estatísticas.\n"
        "- NÃO altere os valores de accuracy, mastery ou trend.\n"
        "- Use os dados fornecidos como base.\n"
        "- Máximo 3 parágrafos.\n\n"
        "Responda APENAS com JSON válido (sem markdown, sem ```).\n"
        "Schema obrigatório:\n"
        "{\n"
        '  "summary": "resumo do desempenho em 1-2 frases",\n'
        '  "strengths": ["ponto forte 1", "ponto forte 2"],\n'
        '  "weaknesses": ["ponto fraco 1", "ponto fraco 2"],\n'
        '  "advice": "conselho prático e personalizado",\n'
        '  "next_step": "próximo passo concreto"\n'
        "}"
    )

    user_msg = (
        f"Gere feedback personalizado para o aluno com base nos dados:\n\n"
        f"Desempenho:\n"
        f"- Acurácia: {data.accuracy:.0%}\n"
        f"- Mastery: {data.mastery:.0%}\n"
        f"- Confiança: {data.confidence:.0%}\n"
        f"- Tendência: {data.trend}\n\n"
        f"Pontos fortes: {strong}\n"
        f"Pontos fracos: {weak}\n\n"
        f"Desempenho recente: {recent_str}\n"
        f"Desempenho histórico: {historical_str}\n\n"
        f"Retorne APENAS o JSON no schema especificado."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _parse_feedback(data: dict) -> FeedbackOutput:
    """Parse e validação da resposta da IA."""
    strengths = data.get("strengths", [])
    if not isinstance(strengths, list):
        strengths = [str(strengths)]
    strengths = [_sanitize_text(str(s)) for s in strengths if str(s).strip()]

    weaknesses = data.get("weaknesses", [])
    if not isinstance(weaknesses, list):
        weaknesses = [str(weaknesses)]
    weaknesses = [_sanitize_text(str(w)) for w in weaknesses if str(w).strip()]

    return FeedbackOutput(
        summary=_sanitize_text(str(data.get("summary", ""))),
        strengths=strengths[:5],
        weaknesses=weaknesses[:5],
        advice=_sanitize_text(str(data.get("advice", ""))),
        next_step=_sanitize_text(str(data.get("next_step", ""))),
    )


def _fallback_feedback(data: PerformanceData) -> FeedbackOutput:
    """Feedback de fallback quando a IA falha."""
    acc_pct = f"{data.accuracy:.0%}"

    trend_desc = {
        "melhorando": "seu desempenho está melhorando",
        "estavel": "seu desempenho está estável",
        "piorando": "seu desempenho está em queda",
    }.get(data.trend.lower(), f"sua tendência é {data.trend}")

    strong = data.strong_points[:3] if data.strong_points else ["Áreas com desempenho positivo"]
    weak = data.weak_points[:3] if data.weak_points else ["Áreas que precisam de atenção"]

    return FeedbackOutput(
        summary=f"Sua acurácia atual é {acc_pct}. {trend_desc.capitalize()}.",
        strengths=strong,
        weaknesses=weak,
        advice=(
            f"Com mastery de {data.mastery:.0%} e confiança de {data.confidence:.0%}, "
            f"continue focando nos pontos fracos identificados."
        ),
        next_step=f"Revise os tópicos: {', '.join(weak[:2])} antes da próxima avaliação.",
    )


class FeedbackGenerator:
    """
    Gerador de feedback usando IA generativa.

    Usa AIClient exclusivamente. Nunca faz chamadas HTTP diretas.
    Implementa cache, sanitização e fallback.

    REGRA DE OURO: A IA apenas personaliza.
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

    def _cache_key(self, data: PerformanceData) -> str:
        """Gera chave de cache baseada nos dados de desempenho."""
        raw = (
            f"{data.accuracy:.4f}|{data.mastery:.4f}|{data.confidence:.4f}|"
            f"{data.trend}|{','.join(data.strong_points)}|"
            f"{','.join(data.weak_points)}|{PROMPT_VERSION}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _is_cache_valid(self, key: str) -> bool:
        """Verifica se entrada de cache ainda é válida."""
        entry = self._cache.get(key)
        if not entry:
            return False
        elapsed = time.monotonic() - entry.created_at
        return elapsed < self._cache_ttl

    def generate(self, data: PerformanceData) -> FeedbackOutput:
        """
        Gera feedback personalizado.

        Args:
            data: Dados de desempenho do backend.

        Returns:
            FeedbackOutput com feedback estruturado.
        """
        if not self._client.enabled:
            logger.warning("IA desligada, usando fallback para feedback")
            return _fallback_feedback(data)

        cache_key = self._cache_key(data)
        if self._is_cache_valid(cache_key):
            logger.info("Cache hit para feedback")
            return self._cache[cache_key].output

        messages = _build_feedback_prompt(data)
        chat_messages = [Message(role=m["role"], content=m["content"]) for m in messages]
        request = ChatRequest(
            messages=chat_messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
        )

        try:
            structured = self._client.chat_structured(
                request,
                expected_keys=["summary", "strengths", "weaknesses", "advice", "next_step"],
                feature="feedback",
            )
            output = _parse_feedback(structured.data)
        except (AIError, AIValidationError, Exception) as exc:
            logger.warning("Erro ao gerar feedback: %s. Usando fallback.", exc)
            return _fallback_feedback(data)

        self._cache[cache_key] = _CacheEntry(
            output=output,
            created_at=time.monotonic(),
        )

        return output

    def get_cached(self, data: PerformanceData) -> FeedbackOutput | None:
        """Retorna feedback em cache (se válido)."""
        key = self._cache_key(data)
        if self._is_cache_valid(key):
            return self._cache[key].output
        return None

    def clear_cache(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()

    def __repr__(self) -> str:
        return (
            f"FeedbackGenerator(cache_ttl={self._cache_ttl}, "
            f"max_tokens={self._max_tokens})"
        )
