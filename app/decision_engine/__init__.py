"""
Decision Engine - PlanejaENEM 4.0.

Motor central de decisão que gera recomendações de estudo.
Todas as decisões são determinísticas e não utilizam IA generativa.

Módulos:
- types: Enums, dataclasses e tipos
- ranking: Pesos centralizados e cálculo de scores
- policies: Detecção e resolução de conflitos
- explanations: Reason codes → texto amigável
- engine: Ciclo completo de decisão
- simulator: Simulação e comparação de planos
- routes: Endpoints da API
"""

from app.decision_engine.engine import (
    build_debug_output,
    generate_recommendations,
    get_current_recommendations,
    get_recommendation_history,
)
from app.decision_engine.explanations import (
    build_debug_explanation,
    build_explanation,
    build_short_explanation,
    get_action_text,
    get_mastery_level_text,
)
from app.decision_engine.policies import (
    detect_all_conflicts,
    resolve_conflicts,
)
from app.decision_engine.ranking import calculate_final_score
from app.decision_engine.routes import decision_engine_bp
from app.decision_engine.simulator import (
    compare_plans,
    generate_comparison_report,
    simulate_plan,
    simulate_scenario,
)
from app.decision_engine.types import (
    Conflict,
    ConflictSeverity,
    ConflictType,
    MasteryLevel,
    ReasonCode,
    SessionStatus,
    StudyAction,
    StudyPhase,
    StudyRecommendation,
    StudySlot,
    TopicContext,
    WeeklyAvailability,
)

__all__ = [
    "calculate_final_score",
    "generate_recommendations",
    "get_current_recommendations",
    "get_recommendation_history",
    "build_debug_output",
    "build_explanation",
    "build_short_explanation",
    "build_debug_explanation",
    "get_action_text",
    "get_mastery_level_text",
    "detect_all_conflicts",
    "resolve_conflicts",
    "simulate_plan",
    "simulate_scenario",
    "compare_plans",
    "generate_comparison_report",
    "Conflict",
    "ConflictSeverity",
    "ConflictType",
    "MasteryLevel",
    "ReasonCode",
    "SessionStatus",
    "StudyAction",
    "StudyPhase",
    "StudyRecommendation",
    "StudySlot",
    "TopicContext",
    "WeeklyAvailability",
]
