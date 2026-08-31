"""
Ranking Determinístico - PlanejaENEM 4.0.

Calcula o score final de prioridade para cada tópico/assunto.
Os pesos são heurísticas centralizadas e documentadas.

ATENÇÃO: Os pesos são heurísticas determinísticas e podem ser
ajustados posteriormente com base em validação empírica.
Não utilizam IA generativa, LLM ou machine learning.
"""

from datetime import date, timedelta
from typing import Optional

from app.decision_engine.types import (
    MasteryLevel,
    ReasonCode,
    StudyAction,
    StudyPhase,
    TopicContext,
)


# =============================================================================
# PESOS CENTRALIZADOS - HEURÍSTICAS AJUSTÁVEIS
# =============================================================================
# Documentação: Estes pesos são heurísticas e podem ser ajustados
# posteriormente com base em validação empírica.
#
# A soma dos pesos deve ser sempre 1.0 (100%).
#
# Cada peso representa a importância relativa de um fator
# no cálculo do score final de prioridade.
# =============================================================================

WEIGHTS = {
    "need_score": 0.25,
    "weakness": 0.20,
    "recency": 0.15,
    "exam_urgency": 0.15,
    "review_urgency": 0.10,
    "historical_importance": 0.10,
    "study_consistency": 0.05,
}

# Constantes auxiliares
MIN_QUESTIONS_FOR_CONFIDENCE = 3
HIGH_MASTERY_THRESHOLD = 70
LOW_MASTERY_THRESHOLD = 40
POOR_RECENT_ACCURACY = 50
OVERDUE_REVIEW_DAYS = 7


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divisão segura que retorna default quando denominador é zero."""
    if denominator <= 0:
        return default
    return numerator / denominator


def calculate_need_score(context: TopicContext) -> float:
    """
    Calcula o score de necessidade de estudo (0-100).
    
    Considera:
    - Domínio atual (inverso)
    - Desempenho recente
    - Dificuldade da matéria
    - Proximidade do ENEM
    - Revisões atrasadas
    - Confiança estatística
    """
    # Fator de domínio baixo (inverso)
    if context.mastery_score <= 0:
        low_mastery = 100.0
    elif context.mastery_score >= HIGH_MASTERY_THRESHOLD:
        low_mastery = 0.0
    else:
        low_mastery = 100.0 - context.mastery_score

    # Fator de desempenho recente ruim
    if context.recent_accuracy is None:
        recent_poor = 50.0
    elif context.recent_accuracy < POOR_RECENT_ACCURACY:
        recent_poor = 100.0 - context.recent_accuracy
    else:
        recent_poor = 0.0

    if (
        context.historical_accuracy is not None
        and context.recent_accuracy is not None
        and context.recent_accuracy < context.historical_accuracy
    ):
        drop = context.historical_accuracy - context.recent_accuracy
        recent_poor = min(100.0, recent_poor + drop)

    # Fator de dificuldade da matéria
    subject_diff = max(0.0, min(100.0, ((context.subject_difficulty - 1) / 4.0) * 100.0))

    # Fator de proximidade do ENEM
    if context.days_until_exam <= 0:
        exam_prox = 100.0
    elif context.days_until_exam <= 14:
        exam_prox = 95.0
    elif context.days_until_exam <= 30:
        exam_prox = 85.0
    elif context.days_until_exam <= 60:
        exam_prox = 70.0
    elif context.days_until_exam <= 120:
        exam_prox = 50.0
    elif context.days_until_exam <= 180:
        exam_prox = 35.0
    else:
        exam_prox = 20.0

    # Fator de revisão atrasada
    if context.last_review_at is None:
        overdue_rev = 80.0
    else:
        days_since = (date.today() - context.last_review_at).days
        if days_since <= 3:
            overdue_rev = 10.0
        elif days_since <= 7:
            overdue_rev = 30.0
        elif days_since <= 14:
            overdue_rev = 60.0
        elif days_since <= 30:
            overdue_rev = 80.0
        else:
            overdue_rev = 100.0

    # Fator de confiança (inverso)
    confidence = 100.0 - context.confidence_score

    # Cálculo ponderado
    need = (
        low_mastery * 0.30
        + recent_poor * 0.20
        + subject_diff * 0.15
        + exam_prox * 0.15
        + overdue_rev * 0.10
        + confidence * 0.10
    )

    return round(max(0.0, min(100.0, need)), 2)


def calculate_weakness_score(context: TopicContext) -> float:
    """
    Calcula o score de fraqueza (0-100).
    
    Considera domínio, tendência e consistência.
    Quanto mais fraco o aluno no assunto, maior o score.
    """
    # Base: inverso do domínio
    weakness = 100.0 - context.mastery_score

    # Penalidade por tendência de queda
    if (
        context.recent_accuracy is not None
        and context.historical_accuracy is not None
        and context.recent_accuracy < context.historical_accuracy - 10
    ):
        weakness = min(100.0, weakness + 15.0)

    # Penalidade por erros consecutivos
    if context.consecutive_wrong >= 3:
        weakness = min(100.0, weakness + 20.0)
    elif context.consecutive_wrong >= 2:
        weakness = min(100.0, weakness + 10.0)

    return round(max(0.0, min(100.0, weakness)), 2)


def calculate_recency_score(context: TopicContext) -> float:
    """
    Calcula o score de recência (0-100).
    
    Considera quando foi a última atividade no assunto.
    Inatividade prolongada = maior necessidade de estudo.
    """
    if context.last_attempt_at is None and context.last_review_at is None:
        return 80.0

    last_activity = context.last_attempt_at
    if context.last_review_at and (
        last_activity is None or context.last_review_at > last_activity
    ):
        last_activity = context.last_review_at

    if last_activity is None:
        return 80.0

    days_inactive = (date.today() - last_activity).days

    if days_inactive <= 1:
        return 10.0
    elif days_inactive <= 3:
        return 25.0
    elif days_inactive <= 7:
        return 45.0
    elif days_inactive <= 14:
        return 65.0
    elif days_inactive <= 30:
        return 80.0
    else:
        return 100.0


def calculate_exam_urgency_score(context: TopicContext) -> float:
    """
    Calcula o score de urgência do ENEM (0-100).
    
    Quanto mais próximo o ENEM, maior a urgência.
    """
    if context.days_until_exam <= 0:
        return 100.0
    elif context.days_until_exam <= 7:
        return 95.0
    elif context.days_until_exam <= 14:
        return 90.0
    elif context.days_until_exam <= 30:
        return 80.0
    elif context.days_until_exam <= 60:
        return 65.0
    elif context.days_until_exam <= 120:
        return 45.0
    elif context.days_until_exam <= 180:
        return 30.0
    else:
        return 15.0


def calculate_review_urgency_score(context: TopicContext) -> float:
    """
    Calcula o score de urgência de revisão (0-100).
    
    Considera revisões atrasadas e tempo desde a última revisão.
    """
    if context.overdue_reviews > 0:
        if context.overdue_reviews >= 3:
            return 100.0
        elif context.overdue_reviews == 2:
            return 75.0
        else:
            return 50.0

    if context.last_review_at is None:
        return 70.0

    days_since = (date.today() - context.last_review_at).days

    if days_since <= 3:
        return 10.0
    elif days_since <= 7:
        return 30.0
    elif days_since <= 14:
        return 55.0
    elif days_since <= 30:
        return 75.0
    else:
        return 90.0


def calculate_historical_importance_score(context: TopicContext) -> float:
    """
    Calcula o score de importância histórica (0-100).
    
    Considera a prioridade definida pelo usuário e a dificuldade.
    """
    priority_factor = (context.subject_priority / 5.0) * 100.0
    difficulty_factor = (context.subject_difficulty / 5.0) * 100.0

    importance = (priority_factor * 0.6) + (difficulty_factor * 0.4)

    return round(max(0.0, min(100.0, importance)), 2)


def calculate_study_consistency_score(context: TopicContext) -> float:
    """
    Calcula o score de consistência de estudo (0-100).
    
    Penaliza assuntos com muitas sessões perdidas.
    """
    if context.missed_sessions <= 0:
        return 50.0

    if context.missed_sessions >= 5:
        return 10.0
    elif context.missed_sessions >= 3:
        return 25.0
    elif context.missed_sessions >= 1:
        return 40.0

    return 50.0


def determine_reason_codes(
    context: TopicContext,
    components: dict,
) -> list[ReasonCode]:
    """
    Determina os reason codes baseado nos componentes calculados.
    """
    codes = []

    if context.mastery_score < LOW_MASTERY_THRESHOLD:
        codes.append(ReasonCode.LOW_MASTERY)
    elif context.mastery_score < HIGH_MASTERY_THRESHOLD:
        codes.append(ReasonCode.MODERATE_MASTERY)

    if context.recent_accuracy is not None and context.recent_accuracy < POOR_RECENT_ACCURACY:
        codes.append(ReasonCode.RECENT_POOR_PERFORMANCE)

    if (
        context.recent_accuracy is not None
        and context.historical_accuracy is not None
        and context.recent_accuracy < context.historical_accuracy - 10
    ):
        codes.append(ReasonCode.PERFORMANCE_DECLINING)

    if context.overdue_reviews > 0:
        codes.append(ReasonCode.OVERDUE_REVIEW)

    if context.days_until_exam <= 30:
        codes.append(ReasonCode.EXAM_URGENCY)

    if context.subject_difficulty >= 4:
        codes.append(ReasonCode.HIGH_DIFFICULTY)

    if context.confidence_score < 40:
        codes.append(ReasonCode.LOW_CONFIDENCE)

    if context.missed_sessions > 0:
        codes.append(ReasonCode.MISSED_SESSION)

    if context.questions_answered < MIN_QUESTIONS_FOR_CONFIDENCE:
        codes.append(ReasonCode.NO_DATA)

    return codes


def determine_action(
    context: TopicContext,
    study_phase: StudyPhase,
) -> StudyAction:
    """
    Determina a ação de estudo recomendada.
    
    Baseado no domínio atual e fase de estudo.
    """
    mastery = context.mastery_score

    if mastery < 40:
        return StudyAction.LEARN
    elif mastery < 60:
        return StudyAction.PRACTICE
    elif mastery < 75:
        return StudyAction.ENEM_QUESTIONS
    elif mastery < 90:
        if study_phase == StudyPhase.FINAL_STRETCH:
            return StudyAction.ENEM_QUESTIONS
        return StudyAction.DIFFICULT_QUESTIONS
    else:
        if study_phase == StudyPhase.FINAL_STRETCH:
            return StudyAction.REVIEW
        return StudyAction.DIFFICULT_QUESTIONS


def estimate_duration(
    action: StudyAction,
    mastery_score: float,
    study_phase: StudyPhase,
) -> int:
    """
    Estima a duração recomendada da sessão em minutos.
    
    Considera a ação, domínio e fase de estudo.
    """
    base_durations = {
        StudyAction.LEARN: 45,
        StudyAction.PRACTICE: 40,
        StudyAction.ENEM_QUESTIONS: 35,
        StudyAction.REVIEW: 25,
        StudyAction.DIFFICULT_QUESTIONS: 40,
        StudyAction.MOCK_EXAM: 60,
    }

    duration = base_durations.get(action, 30)

    if mastery_score < 30:
        duration = int(duration * 1.3)
    elif mastery_score > 80:
        duration = int(duration * 0.8)

    if study_phase == StudyPhase.FINAL_STRETCH:
        duration = int(duration * 0.9)

    return max(20, min(120, duration))


def calculate_final_score(context: TopicContext) -> dict:
    """
    Calcula o score final de prioridade (0-100).
    
   Esta é a função principal do ranking. Ela combina todos os
    componentes em um único score que determina a prioridade
    do tópico no plano de estudo.
    
    Retorna dict com:
    - final_score: float (0-100)
    - components: dict com cada componente individual
    - weights: dict com os pesos utilizados
    - reason_codes: lista de códigos de motivo
    - recommended_action: ação de estudo recomendada
    - recommended_duration: duração estimada em minutos
    """
    need_score = calculate_need_score(context)
    weakness = calculate_weakness_score(context)
    recency = calculate_recency_score(context)
    exam_urgency = calculate_exam_urgency_score(context)
    review_urgency = calculate_review_urgency_score(context)
    historical_importance = calculate_historical_importance_score(context)
    study_consistency = calculate_study_consistency_score(context)

    final = (
        need_score * WEIGHTS["need_score"]
        + weakness * WEIGHTS["weakness"]
        + recency * WEIGHTS["recency"]
        + exam_urgency * WEIGHTS["exam_urgency"]
        + review_urgency * WEIGHTS["review_urgency"]
        + historical_importance * WEIGHTS["historical_importance"]
        + study_consistency * WEIGHTS["study_consistency"]
    )

    final = round(max(0.0, min(100.0, final)), 2)

    components = {
        "need_score": round(need_score, 2),
        "weakness": round(weakness, 2),
        "recency": round(recency, 2),
        "exam_urgency": round(exam_urgency, 2),
        "review_urgency": round(review_urgency, 2),
        "historical_importance": round(historical_importance, 2),
        "study_consistency": round(study_consistency, 2),
    }

    reason_codes = determine_reason_codes(context, components)

    study_phase = StudyPhase.MEDIUM_TERM
    if context.days_until_exam > 120:
        study_phase = StudyPhase.LONG_TERM
    elif context.days_until_exam <= 30:
        study_phase = StudyPhase.FINAL_STRETCH

    recommended_action = determine_action(context, study_phase)
    recommended_duration = estimate_duration(
        recommended_action, context.mastery_score, study_phase
    )

    return {
        "final_score": final,
        "components": components,
        "weights": WEIGHTS,
        "reason_codes": reason_codes,
        "recommended_action": recommended_action,
        "recommended_duration": recommended_duration,
        "study_phase": study_phase,
    }
