"""
Estimativa de custo do AI Gateway - PlanejaENEM 5.0.

Calcula custo estimado em USD por chamada à IA generativa.
Baseado nos preços do OpenRouter para gpt-4o-mini.

REGRA DE OURO: Estimativa aproximada. Custo real depende do provider.
"""

from __future__ import annotations

from app.ai.config import AIConfig


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    config: AIConfig,
) -> float:
    """
    Calcula custo estimado em USD para uma chamada à IA.

    Args:
        input_tokens: Número de tokens de entrada (prompt).
        output_tokens: Número de tokens de saída (completion).
        config: Configuração do AI Gateway com preços.

    Returns:
        Custo estimado em USD (arredondado para 8 casas decimais).
    """
    if input_tokens <= 0 and output_tokens <= 0:
        return 0.0

    input_cost = (max(0, input_tokens) / 1000.0) * config.cost_per_1k_input_tokens
    output_cost = (max(0, output_tokens) / 1000.0) * config.cost_per_1k_output_tokens
    total = input_cost + output_cost

    return round(total, 8)


def estimate_monthly_cost(
    avg_daily_calls: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
    config: AIConfig,
    days: int = 30,
) -> float:
    """
    Estima custo mensal baseado em uso médio diário.

    Args:
        avg_daily_calls: Média de chamadas por dia.
        avg_input_tokens: Média de tokens de entrada por chamada.
        avg_output_tokens: Média de tokens de saída por chamada.
        config: Configuração do AI Gateway.
        days: Número de dias no período (padrão: 30).

    Returns:
        Custo estimado mensal em USD.
    """
    daily_cost = avg_daily_calls * estimate_cost(
        avg_input_tokens, avg_output_tokens, config
    )
    return round(daily_cost * days, 2)
