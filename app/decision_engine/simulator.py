"""
Simulador de Planos - PlanejaENEM 4.0.

Permite comparar diferentes planos de estudo e avaliar
o impacto esperado de cada um.

Não afirma prever nota do ENEM.
Usa linguagem de "cobertura de prioridades" e "adequação ao perfil".
"""

from datetime import date, timedelta
from typing import Optional

from app.decision_engine.engine import generate_recommendations
from app.decision_engine.types import (
    PlanSimulation,
    StudyRecommendation,
    WeeklyAvailability,
)


def calculate_coverage_score(
    recommendations: list[StudyRecommendation],
    all_contexts: list,
) -> float:
    """
    Calcula a cobertura de prioridades do plano.
    
    Retorna um score de 0-100 indicando quão bem o plano
    cobre os assuntos mais importantes.
    """
    if not recommendations or not all_contexts:
        return 0.0

    total_weight = 0.0
    covered_weight = 0.0

    for context in all_contexts:
        weight = (100.0 - context.mastery_score) * (context.subject_priority / 5.0)
        total_weight += weight

        for rec in recommendations:
            if rec.subject_id == context.subject_id:
                covered_weight += weight * (rec.duration_minutes / 60.0)
                break

    if total_weight <= 0:
        return 100.0

    coverage = (covered_weight / total_weight) * 100.0
    return round(max(0.0, min(100.0, coverage)), 2)


def calculate_priority_coverage(
    recommendations: list[StudyRecommendation],
    all_contexts: list,
) -> dict:
    """
    Calcula a cobertura por faixa de prioridade.
    """
    high_priority = [c for c in all_contexts if c.subject_priority >= 4]
    medium_priority = [c for c in all_contexts if 2 <= c.subject_priority < 4]
    low_priority = [c for c in all_contexts if c.subject_priority < 2]

    covered_high = sum(
        1 for c in high_priority
        if any(r.subject_id == c.subject_id for r in recommendations)
    )
    covered_medium = sum(
        1 for c in medium_priority
        if any(r.subject_id == c.subject_id for r in recommendations)
    )
    covered_low = sum(
        1 for c in low_priority
        if any(r.subject_id == c.subject_id for r in recommendations)
    )

    return {
        "high_priority": {
            "total": len(high_priority),
            "covered": covered_high,
            "percentage": round(
                (covered_high / len(high_priority) * 100) if high_priority else 0, 1
            ),
        },
        "medium_priority": {
            "total": len(medium_priority),
            "covered": covered_medium,
            "percentage": round(
                (covered_medium / len(medium_priority) * 100) if medium_priority else 0, 1
            ),
        },
        "low_priority": {
            "total": len(low_priority),
            "covered": covered_low,
            "percentage": round(
                (covered_low / len(low_priority) * 100) if low_priority else 0, 1
            ),
        },
    }


def simulate_plan(
    user_id: int,
    exam_date: date,
    availability: WeeklyAvailability,
    plan_name: str = "Plano",
    today: Optional[date] = None,
) -> PlanSimulation:
    """
    Simula um plano de estudo e calcula métricas de qualidade.
    
    Args:
        user_id: ID do usuário
        exam_date: Data da prova
        availability: Disponibilidade semanal
        plan_name: Nome do plano para identificação
        today: Data atual (para testes)
    
    Returns:
        PlanSimulation com métricas do plano
    """
    from app.decision_engine.engine import collect_topic_contexts

    today = today or date.today()

    result = generate_recommendations(
        user_id=user_id,
        exam_date=exam_date,
        availability=availability,
        today=today,
    )

    recommendations = result.get("recommendations", [])

    contexts = collect_topic_contexts(user_id, exam_date, today)

    coverage_score = calculate_coverage_score(recommendations, contexts)

    priority_coverage = calculate_priority_coverage(recommendations, contexts)

    total_minutes = sum(r.duration_minutes for r in recommendations)

    return PlanSimulation(
        plan_name=plan_name,
        total_minutes=total_minutes,
        total_sessions=len(recommendations),
        coverage_score=coverage_score,
        priority_coverage=priority_coverage,
        recommendations=recommendations,
    )


def compare_plans(
    simulation_a: PlanSimulation,
    simulation_b: PlanSimulation,
) -> dict:
    """
    Compara dois planos de estudo.
    
    Retorna análise comparativa indicando qual plano é mais adequado.
    """
    coverage_diff = simulation_a.coverage_score - simulation_b.coverage_score

    if coverage_diff > 10:
        recommendation = "Plano A é mais adequado"
        reasoning = (
            f"Plano A cobre {simulation_a.coverage_score:.1f}% das prioridades, "
            f"enquanto Plano B cobre {simulation_b.coverage_score:.1f}%."
        )
    elif coverage_diff < -10:
        recommendation = "Plano B é mais adequado"
        reasoning = (
            f"Plano B cobre {simulation_b.coverage_score:.1f}% das prioridades, "
            f"enquanto Plano A cobre {simulation_a.coverage_score:.1f}%."
        )
    else:
        recommendation = "Ambos os planos são similares"
        reasoning = (
            f"A diferença de cobertura é pequena ({abs(coverage_diff):.1f}%). "
            f"Considere outros fatores como preferência pessoal."
        )

    high_priority_a = simulation_a.priority_coverage.get("high_priority", {})
    high_priority_b = simulation_b.priority_coverage.get("high_priority", {})

    return {
        "plan_a": {
            "name": simulation_a.plan_name,
            "total_minutes": simulation_a.total_minutes,
            "total_sessions": simulation_a.total_sessions,
            "coverage_score": simulation_a.coverage_score,
            "high_priority_coverage": high_priority_a.get("percentage", 0),
        },
        "plan_b": {
            "name": simulation_b.plan_name,
            "total_minutes": simulation_b.total_minutes,
            "total_sessions": simulation_b.total_sessions,
            "coverage_score": simulation_b.coverage_score,
            "high_priority_coverage": high_priority_b.get("percentage", 0),
        },
        "analysis": {
            "coverage_difference": round(coverage_diff, 2),
            "recommendation": recommendation,
            "reasoning": reasoning,
        },
    }


def simulate_scenario(
    user_id: int,
    exam_date: date,
    base_availability: WeeklyAvailability,
    scenario_name: str,
    daily_minutes_modifier: float = 1.0,
    weekly_goal_modifier: float = 1.0,
    today: Optional[date] = None,
) -> PlanSimulation:
    """
    Simula um cenário com parâmetros modificados.
    
    Útil para responder perguntas como:
    - "E se eu estudar 30 min a mais por dia?"
    - "E se eu reduzir a meta semanal?"
    """
    modified_availability = WeeklyAvailability(
        days=base_availability.days,
        hours=base_availability.hours,
        daily_minutes=int(base_availability.daily_minutes * daily_minutes_modifier),
        weekly_goal_minutes=int(base_availability.weekly_goal_minutes * weekly_goal_modifier),
        max_session_minutes=base_availability.max_session_minutes,
    )

    return simulate_plan(
        user_id=user_id,
        exam_date=exam_date,
        availability=modified_availability,
        plan_name=scenario_name,
        today=today,
    )


def generate_comparison_report(
    simulations: list[PlanSimulation],
) -> str:
    """
    Gera relatório comparativo de múltiplos planos.
    """
    if not simulations:
        return "Nenhum plano para comparar."

    lines = [
        "=" * 70,
        "COMPARAÇÃO DE PLANOS DE ESTUDO",
        "=" * 70,
        "",
        "IMPORTANTE: Esta é uma estimativa de cobertura de prioridades.",
        "O sistema NÃO prevê nota do ENEM. Use como guia de adequação ao perfil.",
        "",
        "-" * 70,
    ]

    for sim in simulations:
        lines.extend([
            f"\nPlano: {sim.plan_name}",
            f"  Tempo total: {sim.total_minutes}min ({sim.total_minutes/60:.1f}h)",
            f"  Sessões: {sim.total_sessions}",
            f"  Cobertura de prioridades: {sim.coverage_score:.1f}%",
            f"  Prioridades altas: {sim.priority_coverage.get('high_priority', {}).get('percentage', 0):.1f}%",
            f"  Prioridades médias: {sim.priority_coverage.get('medium_priority', {}).get('percentage', 0):.1f}%",
            f"  Prioridades baixas: {sim.priority_coverage.get('low_priority', {}).get('percentage', 0):.1f}%",
        ])

    if len(simulations) >= 2:
        best = max(simulations, key=lambda s: s.coverage_score)
        lines.extend([
            "",
            "-" * 70,
            f"\nMelhor plano: {best.plan_name}",
            f"Cobertura: {best.coverage_score:.1f}%",
            "",
            "Lembre-se: A eficácia real depende da consistência nos estudos.",
        ])

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
