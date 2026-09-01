"""
Rastreamento de uso do AI Gateway - PlanejaENEM 5.0.

Registra métricas de chamadas à IA: tokens, latência, custo, sucesso/erro.
NÃO registra prompts, respostas ou dados sensíveis (API key, senhas).

Implementação dupla:
1. Em memória (lista) — para queries rápidas e compatibilidade
2. Persistência no banco (AIUsage) — para auditoria e relatórios

REGRA DE OURO: Nunca armazena dados sensíveis.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Registro individual de uso (in-memory)."""

    feature: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    status: str
    estimated_cost: float = 0.0
    user_id: int | None = None
    prompt_version: str = "1.0"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UsageTracker:
    """
    Rastreador de uso do AI Gateway.

    Interface desacoplada para permitir substituição futura
    por persistência no banco sem alterar o restante do sistema.

    Mantém cache em memória para queries rápidas e persiste no banco
    quando disponível (app context).
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
        estimated_cost: float = 0.0,
        user_id: int | None = None,
        prompt_version: str = "1.0",
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
            estimated_cost: Custo estimado em USD.
            user_id: ID do usuário (opcional).
            prompt_version: Versão do prompt utilizada.
        """
        record = UsageRecord(
            feature=feature,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            status=status,
            estimated_cost=estimated_cost,
            user_id=user_id,
            prompt_version=prompt_version,
        )
        self._records.append(record)

        # Tenta persistir no banco (se disponível)
        self._persist_to_db(record)

        logger.info(
            "AI usage: feature=%s model=%s tokens=%d/%d/%d "
            "latency=%.1fms cost=$%.6f status=%s",
            feature,
            model,
            input_tokens,
            output_tokens,
            total_tokens,
            latency_ms,
            estimated_cost,
            status,
        )

    def _persist_to_db(self, record: UsageRecord) -> None:
        """Tenta persistir registro no banco de dados."""
        try:
            from flask import current_app
            from app.extensions import db
            from app.ai.models import AIUsage

            if not current_app or not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
                return

            usage = AIUsage(
                user_id=record.user_id,
                feature=record.feature,
                model=record.model,
                prompt_version=record.prompt_version,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                total_tokens=record.total_tokens,
                latency_ms=record.latency_ms,
                estimated_cost=record.estimated_cost,
                status=record.status,
                error_type=None if record.status == "success" else record.status,
            )
            db.session.add(usage)
            db.session.commit()
        except Exception as exc:
            # Não falha a aplicação se persistência falhar
            logger.debug("Não foi possível persistir AIUsage: %s", exc)

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
                "total_cost_usd": 0.0,
            }

        total = len(self._records)
        success_count = sum(1 for r in self._records if r.status == "success")
        error_count = total - success_count
        total_in = sum(r.input_tokens for r in self._records)
        total_out = sum(r.output_tokens for r in self._records)
        avg_latency = sum(r.latency_ms for r in self._records) / total
        total_cost = sum(r.estimated_cost for r in self._records)

        return {
            "total_calls": total,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_tokens": total_in + total_out,
            "avg_latency_ms": round(avg_latency, 2),
            "error_rate": round(error_count / total, 4) if total > 0 else 0.0,
            "success_calls": success_count,
            "error_calls": error_count,
            "total_cost_usd": round(total_cost, 8),
        }

    def summary_by_feature(self, hours: int = 24) -> dict:
        """
        Retorna resumo agregado por feature.

        Args:
            hours: Período em horas (padrão: 24).

        Returns:
            Dict com chaves sendo as features e valores sendo métricas.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent = [r for r in self._records if r.timestamp >= cutoff]

        if not recent:
            return {}

        by_feature: dict[str, list[UsageRecord]] = {}
        for record in recent:
            by_feature.setdefault(record.feature, []).append(record)

        result = {}
        for feature, records in by_feature.items():
            total = len(records)
            success = sum(1 for r in records if r.status == "success")
            total_tokens = sum(r.total_tokens for r in records)
            total_cost = sum(r.estimated_cost for r in records)
            avg_latency = sum(r.latency_ms for r in records) / total

            result[feature] = {
                "calls": total,
                "success_calls": success,
                "error_calls": total - success,
                "total_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 8),
                "avg_latency_ms": round(avg_latency, 2),
            }

        return result

    def cost_summary(self, period: str = "daily") -> dict:
        """
        Retorna resumo de custos.

        Args:
            period: "daily" ou "monthly".

        Returns:
            Dict com custos agregados.
        """
        now = datetime.now(timezone.utc)

        if period == "monthly":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(hours=24)

        recent = [r for r in self._records if r.timestamp >= cutoff]

        if not recent:
            return {
                "period": period,
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "total_tokens": 0,
            }

        total_cost = sum(r.estimated_cost for r in recent)
        total_tokens = sum(r.total_tokens for r in recent)

        return {
            "period": period,
            "total_cost_usd": round(total_cost, 8),
            "total_calls": len(recent),
            "total_tokens": total_tokens,
        }

    def is_budget_exceeded(
        self,
        daily_budget: float = 5.0,
        monthly_budget: float = 100.0,
    ) -> dict:
        """
        Verifica se o orçamento foi excedido.

        Args:
            daily_budget: Orçamento diário em USD.
            monthly_budget: Orçamento mensal em USD.

        Returns:
            Dict com status do orçamento.
        """
        daily = self.cost_summary("daily")
        monthly = self.cost_summary("monthly")

        return {
            "daily_exceeded": daily["total_cost_usd"] >= daily_budget,
            "monthly_exceeded": monthly["total_cost_usd"] >= monthly_budget,
            "daily_cost": daily["total_cost_usd"],
            "monthly_cost": monthly["total_cost_usd"],
            "daily_budget": daily_budget,
            "monthly_budget": monthly_budget,
        }

    def get_records(self, limit: int | None = None) -> list[UsageRecord]:
        """Retorna cópia da lista de registros (para inspeção)."""
        if limit:
            return list(self._records[-limit:])
        return list(self._records)

    def reset(self) -> None:
        """Limpa todos os registros. Útil para testes."""
        self._records.clear()
