"""
Decision Engine - PlanejaENEM 4.0.

Motor central de decisão que gera recomendações de estudo.
Executa o ciclo completo: coleta dados → calcula scores → rankeia →
detecta conflitos → resolve → aloca tempo → gera recomendações.

Todas as decisões são determinísticas e reproduzíveis.
Não utiliza IA generativa, LLM ou machine learning.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.decision_engine.explanations import (
    build_debug_explanation,
    build_explanation,
    build_short_explanation,
)
from app.decision_engine.policies import (
    detect_all_conflicts,
    resolve_conflicts,
)
from app.decision_engine.ranking import calculate_final_score
from app.decision_engine.types import (
    Conflict,
    MasteryLevel,
    ReasonCode,
    StudyAction,
    StudyPhase,
    StudyRecommendation,
    TopicContext,
    WeeklyAvailability,
)


def collect_topic_contexts(
    user_id: int,
    exam_date: date,
    today: Optional[date] = None,
) -> list[TopicContext]:
    """
    Coleta o contexto completo de todos os tópicos do usuário.
    
    Busca dados de:
    - KnowledgeState (domínio, confiança, tendência)
    - Subject (dificuldade, prioridade, área)
    - Topic (nome)
    - QuestionAttempt (histórico de respostas)
    - StudySession (sessões perdidas)
    """
    from app.extensions import db
    from app.models import Subject, StudySession, Topic
    from app.performance.models import KnowledgeState

    today = today or date.today()
    days_until_exam = max(0, (exam_date - today).days)

    knowledge_states = KnowledgeState.query.filter_by(user_id=user_id).all()

    contexts = []

    for ks in knowledge_states:
        subject = db.session.get(Subject, ks.subject_id)
        if subject is None:
            continue

        topic = db.session.get(Topic, ks.topic_id)
        topic_name = topic.nome if topic else ""

        last_attempt_date = None
        if ks.last_attempt_at:
            last_attempt_date = ks.last_attempt_at.date() if isinstance(ks.last_attempt_at, datetime) else ks.last_attempt_at

        last_review_date = None
        if ks.last_review_at:
            last_review_date = ks.last_review_at.date() if isinstance(ks.last_review_at, datetime) else ks.last_review_at

        missed_count = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.subject_id == subject.id,
            StudySession.session_date < today,
            StudySession.completed == False,
            StudySession.manual_override == False,
        ).count()

        overdue_count = 0
        if ks.last_review_at:
            last_rev = ks.last_review_at
            if isinstance(last_rev, datetime):
                if last_rev.tzinfo is None:
                    last_rev = last_rev.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_rev).days
            else:
                days_since = (today - last_rev).days
            if days_since > 7:
                overdue_count = 1

        context = TopicContext(
            topic_id=ks.topic_id,
            subject_id=ks.subject_id,
            topic_name=topic_name,
            subject_name=subject.nome,
            area=subject.area or "outro",
            mastery_score=ks.mastery_score,
            confidence_score=ks.confidence_score,
            recent_accuracy=ks.recent_accuracy,
            historical_accuracy=ks.historical_accuracy,
            questions_answered=ks.questions_answered,
            questions_correct=ks.questions_correct,
            questions_wrong=ks.questions_wrong,
            consecutive_correct=ks.consecutive_correct,
            consecutive_wrong=ks.consecutive_wrong,
            last_attempt_at=last_attempt_date,
            last_review_at=last_review_date,
            subject_difficulty=subject.dificuldade,
            subject_priority=subject.prioridade,
            days_until_exam=days_until_exam,
            overdue_reviews=overdue_count,
            missed_sessions=missed_count,
        )

        contexts.append(context)

    return contexts


def create_recommendation(
    context: TopicContext,
    ranking_result: dict,
    recommended_date: date,
    availability: WeeklyAvailability,
) -> StudyRecommendation:
    """
    Cria uma recomendação de estudo a partir do ranking.
    """
    duration = min(
        ranking_result["recommended_duration"],
        availability.max_session_minutes,
    )

    explanation = build_explanation(
        ranking_result["reason_codes"],
        context,
    )

    short_explanation = build_short_explanation(
        ranking_result["reason_codes"],
    )

    return StudyRecommendation(
        priority=1,
        subject_id=context.subject_id,
        topic_id=context.topic_id,
        action=ranking_result["recommended_action"],
        duration_minutes=duration,
        recommended_date=recommended_date,
        score=ranking_result["final_score"],
        mastery_score=context.mastery_score,
        confidence_score=context.confidence_score,
        reason_codes=ranking_result["reason_codes"],
        explanation=short_explanation,
        study_phase=ranking_result["study_phase"],
        area=context.area,
        subject_name=context.subject_name,
        topic_name=context.topic_name,
    )


def allocate_time(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
) -> list[StudyRecommendation]:
    """
    Aloca o tempo disponível entre as recomendações.
    
    Respeita:
    - Meta semanal
    - Limite diário
    - Duração máxima por sessão
    """
    total_recommended = sum(r.duration_minutes for r in recommendations)

    if total_recommended <= availability.weekly_goal_minutes:
        return recommendations

    scale_factor = availability.weekly_goal_minutes / total_recommended

    adjusted = []
    for rec in recommendations:
        new_duration = max(20, int(rec.duration_minutes * scale_factor))
        new_duration = min(new_duration, availability.max_session_minutes)

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
        adjusted.append(modified)

    return adjusted


def determine_recommended_dates(
    recommendations: list[StudyRecommendation],
    availability: WeeklyAvailability,
    today: Optional[date] = None,
) -> list[StudyRecommendation]:
    """
    Distribui as recomendações ao longo da semana.
    """
    today = today or date.today()

    day_mapping = {
        "seg": 0, "ter": 1, "qua": 2, "qui": 3,
        "sex": 4, "sab": 5, "dom": 6,
    }

    available_weekdays = []
    for day_str in availability.days:
        normalized = day_str.lower().strip()
        if normalized in day_mapping:
            available_weekdays.append(day_mapping[normalized])

    if not available_weekdays:
        return recommendations

    sorted_recs = sorted(recommendations, key=lambda r: r.score, reverse=True)

    dated_recs = []
    current_weekday_idx = 0

    for rec in sorted_recs:
        target_weekday = available_weekdays[current_weekday_idx % len(available_weekdays)]

        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        rec_date = today + timedelta(days=days_ahead)

        modified = StudyRecommendation(
            priority=rec.priority,
            subject_id=rec.subject_id,
            topic_id=rec.topic_id,
            action=rec.action,
            duration_minutes=rec.duration_minutes,
            recommended_date=rec_date,
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
        dated_recs.append(modified)

        current_weekday_idx += 1

    return dated_recs


def generate_recommendations(
    user_id: int,
    exam_date: date,
    availability: WeeklyAvailability,
    today: Optional[date] = None,
) -> dict:
    """
    Gera lista ordenada de recomendações de estudo.
    
    Executa o ciclo completo:
    1. Coletar estado de conhecimento
    2. Calcular scores para cada tópico
    3. Rankear por FinalScore
    4. Detectar conflitos
    5. Resolver conflitos
    6. Alocar tempo disponível
    7. Gerar recomendações com reason codes
    8. Retornar lista ordenada
    
    Retorna dict com:
    - recommendations: lista de recomendações ordenadas
    - conflicts: conflitos detectados
    - unresolved: conflitos não resolvidos
    - summary: resumo do plano
    - debug: informações de debug (se solicitado)
    """
    today = today or date.today()

    contexts = collect_topic_contexts(user_id, exam_date, today)

    if not contexts:
        return {
            "recommendations": [],
            "conflicts": [],
            "unresolved": [],
            "summary": {
                "total_recommendations": 0,
                "total_minutes": 0,
                "topics_analyzed": 0,
            },
            "debug": {},
        }

    ranked = []
    debug_info = {}

    for context in contexts:
        ranking_result = calculate_final_score(context)

        recommendation = create_recommendation(
            context, ranking_result, today, availability
        )
        ranked.append(recommendation)

        debug_info[context.topic_id] = {
            "topic_name": context.topic_name,
            "subject_name": context.subject_name,
            "mastery_score": context.mastery_score,
            "confidence_score": context.confidence_score,
            "final_score": ranking_result["final_score"],
            "components": ranking_result["components"],
            "weights": ranking_result["weights"],
            "reason_codes": [rc.value for rc in ranking_result["reason_codes"]],
            "recommended_action": ranking_result["recommended_action"].value,
        }

    ranked.sort(key=lambda r: r.score, reverse=True)

    for i, rec in enumerate(ranked):
        rec.priority = i + 1

    conflicts = detect_all_conflicts(ranked, availability)

    resolved, unresolved = resolve_conflicts(ranked, availability)

    resolved = allocate_time(resolved, availability)

    resolved = determine_recommended_dates(resolved, availability, today)

    total_minutes = sum(r.duration_minutes for r in resolved)

    summary = {
        "total_recommendations": len(resolved),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 1),
        "topics_analyzed": len(contexts),
        "conflicts_detected": len(conflicts),
        "conflicts_resolved": len(conflicts) - len(unresolved),
        "study_phase": ranked[0].study_phase.value if ranked else "unknown",
        "days_until_exam": (exam_date - today).days,
    }

    return {
        "recommendations": resolved,
        "conflicts": conflicts,
        "unresolved": unresolved,
        "summary": summary,
        "debug": debug_info,
    }


def get_current_recommendations(
    user_id: int,
    today: Optional[date] = None,
) -> Optional[StudyRecommendation]:
    """
    Retorna a recomendação principal para o momento atual.
    
    Usado no dashboard "O que estudar agora?".
    """
    from app.models import StudyPlan

    today = today or date.today()

    plan = StudyPlan.query.filter_by(
        user_id=user_id,
        is_active=True,
    ).order_by(StudyPlan.generated_at.desc()).first()

    if plan is None:
        return None

    availability = WeeklyAvailability(
        days=plan.days_list,
        hours=plan.hours_list,
        daily_minutes=plan.daily_minutes,
        weekly_goal_minutes=plan.user.weekly_goal_minutes if plan.user else 600,
    )

    result = generate_recommendations(
        user_id=user_id,
        exam_date=plan.exam_date,
        availability=availability,
        today=today,
    )

    recommendations = result.get("recommendations", [])

    if not recommendations:
        return None

    return recommendations[0]


def get_recommendation_history(
    user_id: int,
    limit: int = 50,
) -> list[dict]:
    """
    Retorna histórico de recomendações do usuário.
    """
    from app.extensions import db
    from app.models import StudySession

    sessions = StudySession.query.filter_by(
        user_id=user_id,
    ).order_by(
        StudySession.session_date.desc()
    ).limit(limit).all()

    history = []
    for session in sessions:
        history.append({
            "id": session.id,
            "subject_id": session.subject_id,
            "subject_name": session.subject.nome if session.subject else "",
            "session_date": session.session_date.isoformat() if session.session_date else None,
            "duration_minutes": session.duration_minutes,
            "session_type": session.session_type,
            "status": "completed" if session.completed else "scheduled",
            "priority_score": session.priority_score,
        })

    return history


def build_debug_output(
    result: dict,
) -> str:
    """
    Gera saída detalhada de debug para análise do algoritmo.
    """
    lines = [
        "=" * 70,
        "PLANEJAENEM 4.0 - MODO DEBUG",
        "=" * 70,
        "",
        f"Total de tópicos analisados: {result['summary']['topics_analyzed']}",
        f"Total de recomendações: {result['summary']['total_recommendations']}",
        f"Tempo total recomendado: {result['summary']['total_minutes']}min",
        f"Fase de estudo: {result['summary']['study_phase']}",
        f"Dias até o ENEM: {result['summary']['days_until_exam']}",
        f"Conflitos detectados: {result['summary']['conflicts_detected']}",
        f"Conflitos resolvidos: {result['summary']['conflicts_resolved']}",
        "",
        "-" * 70,
        "RECOMENDAÇÕES ORDENADAS:",
        "-" * 70,
    ]

    for i, rec in enumerate(result["recommendations"], 1):
        lines.extend([
            "",
            f"#{i} - {rec.subject_name} → {rec.topic_name}",
            f"    Score: {rec.score:.2f}",
            f"    Domínio: {rec.mastery_score:.1f}%",
            f"    Confiança: {rec.confidence_score:.1f}%",
            f"    Ação: {rec.action.value}",
            f"    Duração: {rec.duration_minutes}min",
            f"    Data: {rec.recommended_date}",
            f"    Motivos: {build_short_explanation(rec.reason_codes)}",
        ])

    if result["unresolved"]:
        lines.extend([
            "",
            "-" * 70,
            "CONFLITOS NÃO RESOLVIDOS:",
            "-" * 70,
        ])
        for conflict in result["unresolved"]:
            lines.append(f"  - {conflict.conflict_type.value}: {conflict.details}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
