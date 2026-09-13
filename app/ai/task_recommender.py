"""Recomendacao de tarefas de estudo baseada no contexto do aluno."""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass

from app.ai.client import AIClient
from app.ai.exceptions import AIError, AIValidationError
from app.ai.prompts import PROMPT_VERSION
from app.ai.schemas import ChatRequest, Message

logger = logging.getLogger(__name__)
_MAX_TEXT_LENGTH = 2000


@dataclass(frozen=True)
class TaskRecommendationInput:
    subjects: list[str]
    weak_subjects: list[str]
    pending_tasks: list[str]
    available_minutes: int = 60
    target_subject: str | None = None


@dataclass(frozen=True)
class TaskRecommendation:
    title: str
    description: str
    subject: str
    study_type: str
    duration_minutes: int
    reason: str
    model: str = ""
    prompt_version: str = PROMPT_VERSION


def _sanitize(value: object, limit: int = _MAX_TEXT_LENGTH) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _build_prompt(inp: TaskRecommendationInput) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "Voce e um tutor do ENEM. Recomende uma unica tarefa pratica e executavel. "
                "Use somente as materias fornecidas. Nao defina prioridade ou dificuldade. "
                "Se houver uma materia obrigatoria, use exatamente essa materia. "
                "Responda apenas JSON valido com title, description, subject, study_type, "
                "duration_minutes e reason. A duracao deve ser um numero entre 15 e o tempo disponivel."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Materias: {', '.join(inp.subjects)}\n"
                f"Materia obrigatoria: {inp.target_subject or 'nenhuma'}\n"
                f"Materias com menor desempenho: {', '.join(inp.weak_subjects) or 'sem dados'}\n"
                f"Tarefas pendentes: {', '.join(inp.pending_tasks[:10]) or 'nenhuma'}\n"
                f"Tempo disponivel hoje: {inp.available_minutes} minutos\n"
                "Escolha a melhor proxima tarefa e retorne somente o JSON."
            ),
        },
    ]


def _fallback(inp: TaskRecommendationInput) -> TaskRecommendation:
    subject = inp.target_subject or (inp.weak_subjects or inp.subjects or ["Matéria do ENEM"])[0]
    duration = max(15, min(inp.available_minutes, 45))
    return TaskRecommendation(
        title=f"Revisar {subject}",
        description=f"Faça uma revisão ativa de {subject} e resolva questões do tema estudado.",
        subject=subject,
        study_type="revisao_e_questoes",
        duration_minutes=duration,
        reason="A recomendação prioriza a matéria com menor desempenho disponível.",
    )


def _parse(data: dict, inp: TaskRecommendationInput, model: str) -> TaskRecommendation:
    subject = _sanitize(data.get("subject"))
    if subject not in inp.subjects:
        raise AIValidationError("A recomendacao retornou uma materia invalida")
    if inp.target_subject and subject != inp.target_subject:
        raise AIValidationError("A recomendacao nao respeitou a materia obrigatoria")
    duration = int(data.get("duration_minutes", 0))
    if duration < 15 or duration > inp.available_minutes:
        raise AIValidationError("A duracao retornada esta fora do tempo disponivel")
    return TaskRecommendation(
        title=_sanitize(data.get("title"), 200),
        description=_sanitize(data.get("description")),
        subject=subject,
        study_type=_sanitize(data.get("study_type"), 80),
        duration_minutes=duration,
        reason=_sanitize(data.get("reason")),
        model=model,
    )


class TaskRecommender:
    def __init__(self, client: AIClient, max_tokens: int = 220) -> None:
        self._client = client
        self._max_tokens = max_tokens

    def generate(self, inp: TaskRecommendationInput) -> TaskRecommendation:
        if not self._client.enabled:
            return _fallback(inp)
        messages = [Message(role=item["role"], content=item["content"]) for item in _build_prompt(inp)]
        request = ChatRequest(messages=messages, temperature=0.4, max_tokens=self._max_tokens)
        try:
            response = self._client.chat_structured(
                request,
                expected_keys=["title", "description", "subject", "study_type", "duration_minutes", "reason"],
                feature="task_recommendation",
            )
            return _parse(response.data, inp, response.model)
        except (AIError, AIValidationError, ValueError, TypeError) as exc:
            logger.warning("Erro ao recomendar tarefa: %s. Usando fallback.", exc)
            return _fallback(inp)
