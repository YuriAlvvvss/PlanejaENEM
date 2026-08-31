"""
Gerador de questões por IA - PlanejaENEM 5.0.

Gera questões de múltipla escolha usando IA generativa via AIClient.
Inclui cache, limites de taxa, validação e geração em lote.

REGRA DE OURO: A IA APENAS gera conteúdo.
Banco de dados, estatísticas, regras determinísticas,
KnowledgeState e Decision Engine continuam sendo a fonte da verdade.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

from app.ai.client import AIClient
from app.ai.exceptions import AIError, AIDisabledError, AIValidationError
from app.ai.prompts import PROMPT_VERSION, build_question_generation_prompt
from app.ai.schemas import ChatRequest, Message
from app.ai.validators import ValidationResult, validate_question, sanitize_question

logger = logging.getLogger(__name__)


@dataclass
class QuestionGeneratorConfig:
    """Configuração do gerador de questões."""

    max_per_request: int = 5
    max_per_hour: int = 20
    cache_ttl_seconds: int = 3600
    batch_max_tokens: int = 1500


@dataclass(frozen=True)
class GeneratedQuestion:
    """Questão gerada e validada."""

    statement: str
    alternative_a: str
    alternative_b: str
    alternative_c: str
    alternative_d: str
    alternative_e: str
    correct_answer: str
    explanation: str
    difficulty: int
    topic: str
    model: str = ""
    prompt_version: str = PROMPT_VERSION
    validation_status: str = "pending"

    def to_db_dict(self) -> dict:
        """Serializa para dict compatível com o model Question do banco."""
        return {
            "enunciado": self.statement,
            "alternativa_a": self.alternative_a,
            "alternativa_b": self.alternative_b,
            "alternativa_c": self.alternative_c,
            "alternativa_d": self.alternative_d,
            "alternativa_e": self.alternative_e,
            "resposta_correta": self.correct_answer,
            "dificuldade": self.difficulty,
            "fonte": f"ai:{self.model}:{self.prompt_version}",
        }


@dataclass
class _CacheEntry:
    """Entrada de cache com timestamp."""

    questions: list[GeneratedQuestion]
    created_at: float


class QuestionGenerator:
    """
    Gerador de questões usando IA generativa.

    Usa AIClient exclusivamente. Nunca faz chamadas HTTP diretas.
    Implementa cache, limites e validação.
    """

    def __init__(
        self,
        client: AIClient,
        config: QuestionGeneratorConfig | None = None,
    ) -> None:
        self._client = client
        self._config = config or QuestionGeneratorConfig()
        self._cache: dict[str, _CacheEntry] = {}
        self._hourly_usage: dict[str, list[float]] = {}

    def _cache_key(self, area: str, materia: str, assunto: str, dificuldade: int) -> str:
        """Gera chave de cache aproximada por combinação."""
        raw = f"{area.lower().strip()}|{materia.lower().strip()}|{assunto.lower().strip()}|{dificuldade}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _is_cache_valid(self, key: str) -> bool:
        """Verifica se entrada de cache ainda é válida."""
        entry = self._cache.get(key)
        if not entry:
            return False
        elapsed = time.monotonic() - entry.created_at
        return elapsed < self._config.cache_ttl_seconds

    def _check_hourly_limit(self, user_id: str) -> bool:
        """Verifica se usuário atingiu limite horário. Retorna True se pode prosseguir."""
        now = time.monotonic()
        cutoff = now - 3600

        if user_id not in self._hourly_usage:
            self._hourly_usage[user_id] = []

        self._hourly_usage[user_id] = [
            t for t in self._hourly_usage[user_id] if t > cutoff
        ]

        return len(self._hourly_usage[user_id]) < self._config.max_per_hour

    def _record_hourly_usage(self, user_id: str, count: int) -> None:
        """Registra uso horário."""
        now = time.monotonic()
        if user_id not in self._hourly_usage:
            self._hourly_usage[user_id] = []
        self._hourly_usage[user_id].extend([now] * count)

    def generate(
        self,
        user_id: str,
        area: str,
        materia: str,
        assunto: str,
        dificuldade: int,
        quantidade: int = 1,
    ) -> list[GeneratedQuestion]:
        """
        Gera um lote de questões validadas.

        Args:
            user_id: ID do usuário (para limites de taxa).
            area: Área do conhecimento.
            materia: Matéria.
            assunto: Assunto específico.
            dificuldade: Nível 1-5.
            quantidade: Número de questões (1 a max_per_request).

        Returns:
            Lista de GeneratedQuestion validadas.

        Raises:
            AIDisabledError: Se IA está desligada.
            AIValidationError: Se resposta da IA é inválida.
            ValueError: Se parâmetros são inválidos.
        """
        if not self._client.enabled:
            raise AIDisabledError()

        quantidade = max(1, min(quantidade, self._config.max_per_request))

        if not self._check_hourly_limit(user_id):
            raise ValueError(
                f"Limite horário atingido: {self._config.max_per_hour} questões/hora"
            )

        cache_key = self._cache_key(area, materia, assunto, dificuldade)
        if self._is_cache_valid(cache_key):
            cached = self._cache[cache_key].questions
            result = cached[:quantidade]
            self._record_hourly_usage(user_id, len(result))
            logger.info(
                "Cache hit: %d questões para %s/%s/%s/d%d",
                len(result), area, materia, assunto, dificuldade,
            )
            return result

        messages = build_question_generation_prompt(
            area=area,
            materia=materia,
            assunto=assunto,
            dificuldade=dificuldade,
            quantidade=quantidade,
        )

        chat_messages = [Message(role=m["role"], content=m["content"]) for m in messages]
        request = ChatRequest(
            messages=chat_messages,
            temperature=0.7,
            max_tokens=self._config.batch_max_tokens,
        )

        structured = self._client.chat_structured(
            request,
            expected_keys=["questions"],
            feature="question_generation",
        )

        raw_questions = structured.data.get("questions", [])
        if not isinstance(raw_questions, list):
            raise AIValidationError("Resposta da IA não contém lista 'questions'")

        generated: list[GeneratedQuestion] = []
        for raw in raw_questions[:quantidade]:
            sanitized = sanitize_question(raw)
            validation = validate_question(sanitized)

            if validation.is_valid:
                q = GeneratedQuestion(
                    statement=sanitized["statement"],
                    alternative_a=sanitized["alternative_a"],
                    alternative_b=sanitized["alternative_b"],
                    alternative_c=sanitized["alternative_c"],
                    alternative_d=sanitized["alternative_d"],
                    alternative_e=sanitized["alternative_e"],
                    correct_answer=sanitized["correct_answer"],
                    explanation=sanitized["explanation"],
                    difficulty=sanitized["difficulty"],
                    topic=sanitized["topic"],
                    model=structured.model,
                    prompt_version=PROMPT_VERSION,
                    validation_status="approved",
                )
                generated.append(q)
            else:
                logger.warning(
                    "Questão rejeitada na validação: %s",
                    "; ".join(validation.errors),
                )

        if generated:
            self._cache[cache_key] = _CacheEntry(
                questions=generated,
                created_at=time.monotonic(),
            )

        self._record_hourly_usage(user_id, len(generated))

        logger.info(
            "Geradas %d/%d questões válidas para %s/%s/%s/d%d",
            len(generated), quantidade, area, materia, assunto, dificuldade,
        )

        return generated

    def generate_single(
        self,
        user_id: str,
        area: str,
        materia: str,
        assunto: str,
        dificuldade: int,
    ) -> GeneratedQuestion | None:
        """Gera uma única questão. Retorna None se nenhuma válida."""
        results = self.generate(
            user_id=user_id,
            area=area,
            materia=materia,
            assunto=assunto,
            dificuldade=dificuldade,
            quantidade=1,
        )
        return results[0] if results else None

    def get_cached(self, area: str, materia: str, assunto: str, dificuldade: int) -> list[GeneratedQuestion]:
        """Retorna questões em cache para a combinação (se válidas)."""
        key = self._cache_key(area, materia, assunto, dificuldade)
        if self._is_cache_valid(key):
            return self._cache[key].questions
        return []

    def clear_cache(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()

    def remaining_hourly(self, user_id: str) -> int:
        """Retorna quantas questões o usuário ainda pode gerar esta hora."""
        now = time.monotonic()
        cutoff = now - 3600
        usage = self._hourly_usage.get(user_id, [])
        usage = [t for t in usage if t > cutoff]
        return max(0, self._config.max_per_hour - len(usage))

    def __repr__(self) -> str:
        return (
            f"QuestionGenerator(max_per_request={self._config.max_per_request}, "
            f"max_per_hour={self._config.max_per_hour})"
        )
