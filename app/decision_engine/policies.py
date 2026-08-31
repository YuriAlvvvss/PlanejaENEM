"""
Políticas de Conflito - PlanejaENEM 4.0.

Detecta e resolve conflitos no planejamento de estudo.
Garante que as recomendações sejam viáveis e respeitem
as restrições de tempo do aluno.
"""

from datetime import date, time, timedelta
from typing import Optional

from app.decision_engine.types import (
    Conflict,
    ConflictSeverity,
    ConflictType,
    StudyRecommendation,
    WeeklyAvailability,
)


def detect_weekly_goal_impossible(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> Optional[Conflict]:
    """
    Detecta se o tempo total recomendado excede a meta semanal.
    """
    total_recommended = sum(r.duration_minutes for r in recommendations)

    if total_recommended > availability.weekly_goal_minutes:
        return Conflict(
            conflict_type=ConflictType.WEEKLY_GOAL_IMPOSSIBLE,
            severity=ConflictSeverity.HIGH,
            details=(
                f"Tempo recomendado ({total_recommended}min) excede "
                f"meta semanal ({availability.weekly_goal_minutes}min)"
            ),
            affected_subjects=[r.subject_id for r in recommendations],
        )

    return None


def detect_excess_sessions(
    recommendations: list[StudyRecommendation],
    max_per_subject: int = 3,
) -> Optional[Conflict]:
    """
    Detecta se há excesso de sessões para o mesmo assunto.
    """
    subject_counts: dict[int, int] = {}
    for r in recommendations:
        subject_counts[r.subject_id] = subject_counts.get(r.subject_id, 0) + 1

    affected = [
        sid for sid, count in subject_counts.items()
        if count > max_per_subject
    ]

    if affected:
        return Conflict(
            conflict_type=ConflictType.EXCESS_SESSIONS,
            severity=ConflictSeverity.MEDIUM,
            details=(
                f"Assuntos {affected} têm mais de {max_per_subject} sessões"
            ),
            affected_subjects=affected,
        )

    return None


def detect_overdue_review_conflict(
    recommendations: list[StudyRecommendation],
) -> Optional[Conflict]:
    """
    Detecta conflito entre revisões atrasadas e conteúdo novo urgente.
    """
    has_overdue = any(
        any(
            code.value == "overdue_review"
            for code in r.reason_codes
        )
        for r in recommendations
    )

    has_new_content = any(
        r.action.value in ("learn", "practice")
        for r in recommendations
    )

    if has_overdue and has_new_content:
        return Conflict(
            conflict_type=ConflictType.OVERDUE_REVIEW_CONFLICT,
            severity=ConflictSeverity.MEDIUM,
            details="Há revisões atrasadas e conteúdo novo recomendado simultaneamente",
        )

    return None


def detect_daily_limit_exceeded(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> Optional[Conflict]:
    """
    Detecta se algum dia excede o limite diário de minutos.
    """
    daily_totals: dict[date, int] = {}
    for r in recommendations:
        daily_totals[r.recommended_date] = (
            daily_totals.get(r.recommended_date, 0) + r.duration_minutes
        )

    exceeded_days = [
        d for d, total in daily_totals.items()
        if total > availability.daily_minutes
    ]

    if exceeded_days:
        return Conflict(
            conflict_type=ConflictType.DAILY_LIMIT_EXCEEDED,
            severity=ConflictSeverity.HIGH,
            details=f"Dias {exceeded_days} excedem limite diário de {availability.daily_minutes}min",
            affected_dates=exceeded_days,
        )

    return None


def detect_no_availability(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> Optional[Conflict]:
    """
    Detecta se não há disponibilidade para acomodar as recomendações.
    """
    if not availability.days or not availability.hours:
        return Conflict(
            conflict_type=ConflictType.NO_AVAILABILITY,
            severity=ConflictSeverity.CRITICAL,
            details="Não há disponibilidade de tempo configurada",
        )

    return None


def detect_subject_imbalance(
    recommendations: list[StudyRecommendation],
) -> Optional[Conflict]:
    """
    Detecta se há desbalanceamento excessivo entre assuntos.
    """
    if len(recommendations) < 2:
        return None

    subject_counts: dict[int, int] = {}
    for r in recommendations:
        subject_counts[r.subject_id] = subject_counts.get(r.subject_id, 0) + 1

    if not subject_counts:
        return None

    max_count = max(subject_counts.values())
    min_count = min(subject_counts.values())

    if max_count > 0 and min_count == 0 and len(subject_counts) > 1:
        return Conflict(
            conflict_type=ConflictType.SUBJECT_IMBALANCE,
            severity=ConflictSeverity.LOW,
            details="Alguns assuntos não têm sessões recomendadas",
        )

    return None


def detect_all_conflicts(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> list[Conflict]:
    """
    Detecta todos os conflitos nas recomendações.
    """
    conflicts = []

    detectors = [
        lambda: detect_no_availability(recommendations, availability),
        lambda: detect_weekly_goal_impossible(recommendations, availability),
        lambda: detect_excess_sessions(recommendations),
        lambda: detect_overdue_review_conflict(recommendations),
        lambda: detect_daily_limit_exceeded(recommendations, availability),
        lambda: detect_subject_imbalance(recommendations),
    ]

    for detector in detectors:
        conflict = detector()
        if conflict:
            conflicts.append(conflict)

    return conflicts


def resolve_weekly_goal_conflict(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> list[StudyRecommendation]:
    """
    Resolve conflito de meta semanal impossível.
    
    Prioriza:
    1. Revisões atrasadas
    2. Assuntos com baixo domínio
    3. Proximidade do ENEM
    """
    sorted_recs = sorted(
        recommendations,
        key=lambda r: (
            any(code.value == "overdue_review" for code in r.reason_codes),
            -r.mastery_score,
            -r.score,
        ),
        reverse=True,
    )

    resolved = []
    remaining_minutes = availability.weekly_goal_minutes

    for rec in sorted_recs:
        if rec.duration_minutes <= remaining_minutes:
            resolved.append(rec)
            remaining_minutes -= rec.duration_minutes
        else:
            if remaining_minutes >= 20:
                modified = StudyRecommendation(
                    priority=rec.priority,
                    subject_id=rec.subject_id,
                    topic_id=rec.topic_id,
                    action=rec.action,
                    duration_minutes=remaining_minutes,
                    recommended_date=rec.recommended_date,
                    score=rec.score,
                    mastery_score=rec.mastery_score,
                    confidence_score=rec.confidence_score,
                    reason_codes=rec.reason_codes,
                    explanation=rec.explanation,
                    study_phase=rec.study_phase,
                    area=rec.area,
                    subject_name=rec.subject_name,
                    topic_name=rec.topic_name,
                )
                resolved.append(modified)
            break

    return resolved


def resolve_excess_sessions_conflict(
    recommendations: list[StudyRecommendation],
    max_per_subject: int = 3,
) -> list[StudyRecommendation]:
    """
    Resolve conflito de excesso de sessões por assunto.
    
    Mantém apenas as N sessões com maior score para cada assunto.
    """
    subject_recs: dict[int, list[StudyRecommendation]] = {}
    for rec in recommendations:
        if rec.subject_id not in subject_recs:
            subject_recs[rec.subject_id] = []
        subject_recs[rec.subject_id].append(rec)

    resolved = []
    for subject_id, recs in subject_recs.items():
        sorted_recs = sorted(recs, key=lambda r: r.score, reverse=True)
        resolved.extend(sorted_recs[:max_per_subject])

    return resolved


def resolve_daily_limit_conflict(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> list[StudyRecommendation]:
    """
    Resolve conflito de limite diário excedido.
    
    Reduz duração das sessões para caber no limite diário.
    """
    daily_totals: dict[date, int] = {}
    for r in recommendations:
        daily_totals[r.recommended_date] = (
            daily_totals.get(r.recommended_date, 0) + r.duration_minutes
        )

    resolved = []
    for rec in recommendations:
        day_total = daily_totals.get(rec.recommended_date, 0)

        if day_total > availability.daily_minutes:
            excess = day_total - availability.daily_minutes
            new_duration = max(20, rec.duration_minutes - excess)

            modified = StudyRecommendation(
                priority=rec.priority,
                subject_id=rec.subject_id,
                topic_id=rec.topic_id,
                action=rec.action,
                duration_minutes=new_duration,
                recommended_date=rec.recommended_date,
                score=rec.score,
                mastery_score=rec.mastery_score,
                confidence_score=rec.confidence_score,
                reason_codes=rec.reason_codes,
                explanation=rec.explanation,
                study_phase=rec.study_phase,
                area=rec.area,
                subject_name=rec.subject_name,
                topic_name=rec.topic_name,
            )
            resolved.append(modified)
        else:
            resolved.append(rec)

    return resolved


def resolve_conflicts(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> tuple[list[StudyRecommendation], list[Conflict]]:
    """
    Resolve todos os conflitos detectados.
    
    Retorna tupla com:
    - lista de recomendações resolvidas
    - lista de conflitos que não puderam ser resolvidos
    """
    conflicts = detect_all_conflicts(recommendations, availability)
    unresolved = []

    resolved = list(recommendations)

    for conflict in conflicts:
        if conflict.conflict_type == ConflictType.WEEKLY_GOAL_IMPOSSIBLE:
            resolved = resolve_weekly_goal_conflict(resolved, availability)
        elif conflict.conflict_type == ConflictType.EXCESS_SESSIONS:
            resolved = resolve_excess_sessions_conflict(resolved)
        elif conflict.conflict_type == ConflictType.DAILY_LIMIT_EXCEEDED:
            resolved = resolve_daily_limit_conflict(resolved, availability)
        elif conflict.conflict_type == ConflictType.NO_AVAILABILITY:
            unresolved.append(conflict)
        else:
            unresolved.append(conflict)

    return resolved, unresolved
