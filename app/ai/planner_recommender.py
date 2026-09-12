"""Orientacoes da IA para distribuicao de sessoes do cronograma."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai.client import AIClient
from app.ai.exceptions import AIError, AIValidationError
from app.ai.prompts import PROMPT_VERSION
from app.ai.schemas import ChatRequest, Message

logger = logging.getLogger(__name__)
_ALLOWED_TYPES = {"teoria", "exercicios", "questoes_enem", "revisao", "simulado"}


@dataclass(frozen=True)
class PlannerRecommendationInput:
    subjects: list[dict]
    days_until_exam: int


@dataclass(frozen=True)
class PlannerGuidance:
    study_types: dict[str, str]
    reason: str
    model: str = ""
    prompt_version: str = PROMPT_VERSION


def _fallback(inp: PlannerRecommendationInput) -> PlannerGuidance:
    study_types = {}
    for subject in inp.subjects:
        level = subject.get("performance", "medium")
        if level in {"very_low", "low"}:
            study_types[subject["name"]] = "teoria"
        elif inp.days_until_exam <= 30:
            study_types[subject["name"]] = "questoes_enem"
        else:
            study_types[subject["name"]] = "exercicios"
    return PlannerGuidance(
        study_types=study_types,
        reason="A distribuicao considera desempenho, fase de estudos e proximidade da prova.",
    )


def _build_prompt(inp: PlannerRecommendationInput) -> list[dict]:
    subject_text = "\n".join(
        f"- {item['name']}: desempenho {item.get('performance', 'sem dados')}"
        for item in inp.subjects
    )
    return [
        {
            "role": "system",
            "content": (
                "Voce e um planejador do ENEM. Escolha o tipo de estudo mais adequado para cada materia. "
                "Nao crie datas, horarios, prioridades ou dificuldades. Use somente os tipos teoria, "
                "exercicios, questoes_enem, revisao e simulado. Responda apenas JSON valido no formato "
                "{\"recommendations\":[{\"subject\":\"nome\",\"study_type\":\"tipo\"}],\"reason\":\"texto\"}."
            ),
        },
        {
            "role": "user",
            "content": f"Dias ate a prova: {inp.days_until_exam}\nMaterias:\n{subject_text}",
        },
    ]


class PlannerRecommender:
    def __init__(self, client: AIClient, max_tokens: int = 600) -> None:
        self._client = client
        self._max_tokens = max_tokens

    def generate(self, inp: PlannerRecommendationInput) -> PlannerGuidance:
        if not self._client.enabled:
            return _fallback(inp)
        request = ChatRequest(
            messages=[Message(role=item["role"], content=item["content"]) for item in _build_prompt(inp)],
            temperature=0.3,
            max_tokens=self._max_tokens,
        )
        try:
            response = self._client.chat_structured(
                request,
                expected_keys=["recommendations", "reason"],
                feature="planner_recommendation",
            )
            recommendations = response.data.get("recommendations", [])
            names = {item["name"] for item in inp.subjects}
            study_types = {
                item.get("subject"): item.get("study_type")
                for item in recommendations
                if item.get("subject") in names and item.get("study_type") in _ALLOWED_TYPES
            }
            if not study_types:
                raise AIValidationError("A IA nao retornou orientacoes validas")
            return PlannerGuidance(
                study_types=study_types,
                reason=str(response.data.get("reason", ""))[:500],
                model=response.model,
            )
        except (AIError, AIValidationError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Erro ao recomendar cronograma: %s. Usando fallback.", exc)
            return _fallback(inp)
