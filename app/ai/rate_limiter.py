"""
Rate Limiter do AI Gateway - PlanejaENEM 5.0.

Rate limiting por feature + usuário e controle de orçamento.
Implementação in-memory (sobrevive apenas durante a vida do processo).

REGRA DE OURO: Bloqueia apenas recursos de IA não essenciais.
Planner, dashboard, estatísticas e questões existentes sempre funcionam.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.ai.config import AIConfig

logger = logging.getLogger(__name__)

# Features que NÃO são bloqueadas pelo rate limiter (essenciais)
ESSENTIAL_FEATURES = frozenset({
    "planner",
    "dashboard",
    "statistics",
    "decision_engine",
    "questions_existing",
})

# Mapeamento feature -> limite por hora
_FEATURE_LIMIT_KEY = {
    "question_generation": "max_questions_per_hour",
    "explanation": "max_explanations_per_hour",
    "review": "max_reviews_per_hour",
    "feedback": "max_feedback_per_hour",
}


@dataclass
class _UserWindow:
    """Janela de tempo para um usuário."""

    timestamps: list[float] = field(default_factory=list)

    def prune(self, cutoff: float) -> None:
        """Remove timestamps fora da janela."""
        self.timestamps = [t for t in self.timestamps if t > cutoff]

    def count(self, cutoff: float) -> int:
        """Conta registros dentro da janela."""
        self.prune(cutoff)
        return len(self.timestamps)

    def record(self) -> None:
        """Registra um evento agora."""
        self.timestamps.append(time.monotonic())


class AIRateLimiter:
    """
    Rate limiter por feature + controle de orçamento.

    Implementação in-memory. Não persiste entre reinícios.
    """

    def __init__(self, config: AIConfig) -> None:
        self._config = config
        self._windows: dict[str, _UserWindow] = {}

    def _window_key(self, user_id: str, feature: str) -> str:
        """Gera chave para a janela de tempo."""
        return f"{user_id}:{feature}"

    def _get_window(self, user_id: str, feature: str) -> _UserWindow:
        """Obtém ou cria janela para o usuário/feature."""
        key = self._window_key(user_id, feature)
        if key not in self._windows:
            self._windows[key] = _UserWindow()
        return self._windows[key]

    def _get_feature_limit(self, feature: str) -> int:
        """Retorna o limite por hora para a feature."""
        limit_key = _FEATURE_LIMIT_KEY.get(feature)
        if limit_key:
            return getattr(self._config, limit_key, 20)
        return self._config.max_questions_per_hour

    def check_rate_limit(self, user_id: str, feature: str) -> bool:
        """
        Verifica se o usuário pode fazer uma chamada para a feature.

        Args:
            user_id: ID do usuário.
            feature: Nome da feature (ex: "explanation", "review").

        Returns:
            True se pode prosseguir, False se atingiu o limite.
        """
        # Features essenciais nunca são bloqueadas
        if feature in ESSENTIAL_FEATURES:
            return True

        limit = self._get_feature_limit(feature)
        now = time.monotonic()
        cutoff = now - 3600

        window = self._get_window(user_id, feature)
        current_count = window.count(cutoff)

        if current_count >= limit:
            logger.warning(
                "Rate limit atingido: user=%s feature=%s count=%d/%d",
                user_id, feature, current_count, limit,
            )
            return False

        return True

    def record_usage(self, user_id: str, feature: str) -> None:
        """
        Registra uso de uma chamada.

        Args:
            user_id: ID do usuário.
            feature: Nome da feature.
        """
        window = self._get_window(user_id, feature)
        window.record()

    def get_remaining(self, user_id: str, feature: str) -> int:
        """
        Retorna quantas chamadas o usuário ainda pode fazer.

        Args:
            user_id: ID do usuário.
            feature: Nome da feature.

        Returns:
            Número de chamadas restantes (pode ser 0 ou negativo).
        """
        limit = self._get_feature_limit(feature)
        now = time.monotonic()
        cutoff = now - 3600

        window = self._get_window(user_id, feature)
        current_count = window.count(cutoff)

        return max(0, limit - current_count)

    def check_budget(self, user_id: str | None) -> bool:
        """
        Verifica se o orçamento foi excedido.

        Args:
            user_id: ID do usuário (None para orçamento global).

        Returns:
            True se dentro do orçamento, False se excedido.
        """
        # Por enquanto, retorna True (orçamento é verificado via banco)
        # Esta implementação pode ser expandida com cache local
        return True

    def reset(self, user_id: str | None = None) -> None:
        """
        Reseta janela de tempo.

        Args:
            user_id: Se fornecido, reseta apenas este usuário.
                     Se None, reseta tudo.
        """
        if user_id is None:
            self._windows.clear()
        else:
            keys_to_remove = [
                k for k in self._windows if k.startswith(f"{user_id}:")
            ]
            for key in keys_to_remove:
                del self._windows[key]

    def get_stats(self, user_id: str | None = None) -> dict:
        """
        Retorna estatísticas de uso.

        Args:
            user_id: Se fornecido, retorna stats deste usuário.
                     Se None, retorna stats globais.

        Returns:
            Dict com estatísticas.
        """
        now = time.monotonic()
        cutoff = now - 3600

        stats = {}
        for key, window in self._windows.items():
            if user_id and not key.startswith(f"{user_id}:"):
                continue

            parts = key.split(":", 1)
            if len(parts) == 2:
                uid, feature = parts
                count = window.count(cutoff)
                limit = self._get_feature_limit(feature)
                stats[feature] = {
                    "user_id": uid,
                    "count": count,
                    "limit": limit,
                    "remaining": max(0, limit - count),
                }

        return stats

    def __repr__(self) -> str:
        return (
            f"AIRateLimiter(features={len(_FEATURE_LIMIT_KEY)}, "
            f"windows={len(self._windows)})"
        )
