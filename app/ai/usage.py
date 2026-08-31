"""
Rastreamento de uso do AI Gateway - PlanejaENEM 5.0.

Registra métricas básicas de chamadas à IA: tokens, latência, sucesso/erro.
NÃO registra prompts, respostas ou dados sensíveis (API key, senhas).

A implementação atual é em memória (lista simples).
Preparada para substituição futura por persistência no banco
sem alterar a interface pública.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Registro individual de uso."""

    feature: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    status: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UsageTracker:
    """
    Rastreador de uso do AI Gateway.

    Interface desacoplada para permitir substituição futura
    por persistência no banco sem alterar o restante do sistema.
    """

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []

    def record(
        self,
        feature: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        latency_ms: float,
        status: str = "success",
    ) -> None:
        """
        Registra uma chamada à IA.

        Args:
            feature: Feature que fez a chamada (ex: "explanation", "summary").
            model: Identificador do modelo utilizado.
            input_tokens: Número de tokens de entrada (prompt).
            output_tokens: Número de tokens de saída (completion).
            total_tokens: Total de tokens utilizados.
            latency_ms: Latência da chamada em milissegundos.
            status: Status da chamada ("success", "error", "timeout", "rate_limit").
        """
        record = UsageRecord(
            feature=feature,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            status=status,
        )
        self._records.append(record)

        logger.info(
            "AI usage: feature=%s model=%s tokens=%d/%d/%d latency=%.1fms status=%s",
            feature,
            model,
            input_tokens,
            output_tokens,
            total_tokens,
            latency_ms,
            status,
        )

    def summary(self) -> dict:
        """
        Retorna resumo agregado do uso.

        Returns:
            Dict com total de chamadas, tokens, latência média, taxa de erro.
        """
        if not self._records:
            return {
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "avg_latency_ms": 0.0,
                "error_rate": 0.0,
                "success_calls": 0,
                "error_calls": 0,
            }

        total = len(self._records)
        success_count = sum(1 for r in self._records if r.status == "success")
        error_count = total - success_count
        total_in = sum(r.input_tokens for r in self._records)
        total_out = sum(r.output_tokens for r in self._records)
        avg_latency = sum(r.latency_ms for r in self._records) / total

        return {
            "total_calls": total,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_tokens": total_in + total_out,
            "avg_latency_ms": round(avg_latency, 2),
            "error_rate": round(error_count / total, 4) if total > 0 else 0.0,
            "success_calls": success_count,
            "error_calls": error_count,
        }

    def get_records(self) -> list[UsageRecord]:
        """Retorna cópia da lista de registros (para inspeção)."""
        return list(self._records)

    def reset(self) -> None:
        """Limpa todos os registros. Útil para testes."""
        self._records.clear()
