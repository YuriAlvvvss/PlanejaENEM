"""
Services de performance - PlanejaENEM 3.0.

Orquestra as operações de análise de desempenho, cálculo de domínio,
atualização de KnowledgeState e recomendações.

Camada central que conecta:
Questões -> Tentativas -> Estatísticas -> KnowledgeState -> Recommendation Engine -> Planner
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.extensions import db
from app.models import Question, QuestionAttempt, Subject, Topic
from app.performance.models import KnowledgeState
from app.performance.mastery import (
    calculate_confidence_score,
    calculate_mastery,
    get_trend,
)
from app.performance.recommendations import calculate_need_score, recommend_next_topic


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divisão segura que retorna default quando denominador é zero."""
    if denominator <= 0:
        return default
    return numerator / denominator


def get_topic_attempt_stats(
    user_id: int,
    topic_id: int,
) -> dict:
    """
    Busca estatísticas de tentativas de um tópico via agregação SQL.

    Evita N+1 queries e não carrega milhares de tentativas para Python.
    """
    from sqlalchemy import func

    # IDs das questões do tópico
    question_ids = (
        db.session.query(Question.id)
        .filter(Question.user_id == user_id, Question.topic_id == topic_id)
        .all()
    )
    question_ids = [q[0] for q in question_ids]

    if not question_ids:
        return {
            "total": 0,
            "correct": 0,
            "wrong": 0,
            "accuracy": 0.0,
            "average_difficulty": 3.0,
            "average_response_time": None,
            "recent_correct": 0,
            "recent_total": 0,
            "recent_accuracy": 0.0,
            "last_attempt_at": None,
            "consecutive_correct": 0,
            "consecutive_wrong": 0,
        }

    # Agregação principal
    stats = (
        db.session.query(
            func.count(QuestionAttempt.id).label("total"),
            func.sum(func.cast(QuestionAttempt.correta, db.Integer)).label("correct"),
            func.max(QuestionAttempt.attempted_at).label("last_attempt_at"),
            func.avg(QuestionAttempt.tempo_segundos).label("avg_time"),
        )
        .filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
        )
        .first()
    )

    total = stats.total or 0
    correct = stats.correct or 0
    wrong = total - correct
    accuracy = (_safe_divide(correct, total)) * 100.0 if total > 0 else 0.0
    last_attempt_at = stats.last_attempt_at
    avg_time = stats.avg_time

    # Dificuldade média das questões
    avg_difficulty = (
        db.session.query(func.avg(Question.dificuldade))
        .filter(
            Question.user_id == user_id,
            Question.id.in_(question_ids),
        )
        .scalar()
        or 3.0
    )

    # Últimas 10 tentativas (janela recente)
    recent_stats = (
        db.session.query(
            func.count(QuestionAttempt.id).label("recent_total"),
            func.sum(func.cast(QuestionAttempt.correta, db.Integer)).label(
                "recent_correct"
            ),
        )
        .filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
        )
        .order_by(QuestionAttempt.attempted_at.desc())
        .limit(10)
        .first()
    )

    recent_total = recent_stats.recent_total or 0
    recent_correct = recent_stats.recent_correct or 0
    recent_accuracy = (
        (_safe_divide(recent_correct, recent_total)) * 100.0 if recent_total > 0 else 0.0
    )

    # Calcular consecutive correct/wrong
    consecutive_correct = 0
    consecutive_wrong = 0

    if total > 0:
        # Buscar últimas tentativas em ordem cronológica
        recent_attempts = (
            db.session.query(QuestionAttempt.correta)
            .filter(
                QuestionAttempt.user_id == user_id,
                QuestionAttempt.question_id.in_(question_ids),
            )
            .order_by(QuestionAttempt.attempted_at.desc())
            .limit(20)
            .all()
        )

        # Contar consecutive da mais recente
        if recent_attempts:
            # Primeiro: consecutive wrong (da mais recente)
            for attempt in recent_attempts:
                if not attempt.correta:
                    consecutive_wrong += 1
                else:
                    break

            # Se não começou com wrong, contar consecutive correct
            if consecutive_wrong == 0:
                for attempt in recent_attempts:
                    if attempt.correta:
                        consecutive_correct += 1
                    else:
                        break

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy,
        "average_difficulty": float(avg_difficulty),
        "average_response_time": float(avg_time) if avg_time else None,
        "recent_correct": recent_correct,
        "recent_total": recent_total,
        "recent_accuracy": recent_accuracy,
        "last_attempt_at": last_attempt_at,
        "consecutive_correct": consecutive_correct,
        "consecutive_wrong": consecutive_wrong,
    }


def get_subject_attempt_stats(
    user_id: int,
    subject_id: int,
) -> dict:
    """
    Busca estatísticas de tentativas de uma matéria via agregação SQL.
    """
    from sqlalchemy import func

    question_ids = (
        db.session.query(Question.id)
        .filter(Question.user_id == user_id, Question.subject_id == subject_id)
        .all()
    )
    question_ids = [q[0] for q in question_ids]

    if not question_ids:
        return {
            "total": 0,
            "correct": 0,
            "wrong": 0,
            "accuracy": 0.0,
            "average_difficulty": 3.0,
        }

    stats = (
        db.session.query(
            func.count(QuestionAttempt.id).label("total"),
            func.sum(func.cast(QuestionAttempt.correta, db.Integer)).label("correct"),
        )
        .filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
        )
        .first()
    )

    total = stats.total or 0
    correct = stats.correct or 0
    wrong = total - correct
    accuracy = (_safe_divide(correct, total)) * 100.0 if total > 0 else 0.0

    avg_difficulty = (
        db.session.query(func.avg(Question.dificuldade))
        .filter(
            Question.user_id == user_id,
            Question.id.in_(question_ids),
        )
        .scalar()
        or 3.0
    )

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy,
        "average_difficulty": float(avg_difficulty),
    }


def update_knowledge_state(
    user_id: int,
    topic_id: int,
    now: Optional[datetime] = None,
) -> KnowledgeState:
    """
    Atualiza o KnowledgeState de um tópico baseado nas tentativas.

    Calcula mastery_score, confidence_score, trend e outros campos.
    Cria o KnowledgeState se não existir.
    """
    now = now or datetime.now(timezone.utc)

    topic = db.session.get(Topic, topic_id)
    if topic is None:
        raise ValueError(f"Topic {topic_id} not found")

    # Buscar ou criar KnowledgeState
    ks = KnowledgeState.query.filter_by(
        user_id=user_id, topic_id=topic_id
    ).first()

    if ks is None:
        ks = KnowledgeState(
            user_id=user_id,
            subject_id=topic.subject_id,
            topic_id=topic_id,
        )
        db.session.add(ks)

    # Buscar estatísticas
    stats = get_topic_attempt_stats(user_id, topic_id)

    # Calcular mastery
    mastery_data = calculate_mastery(
        questions_correct=stats["correct"],
        questions_wrong=stats["wrong"],
        questions_answered=stats["total"],
        recent_correct=stats["recent_correct"],
        recent_total=stats["recent_total"],
        average_difficulty=stats["average_difficulty"],
        consecutive_correct=stats["consecutive_correct"],
        consecutive_wrong=stats["consecutive_wrong"],
        last_attempt_at=stats["last_attempt_at"],
        last_review_at=ks.last_review_at,
        now=now,
    )

    # Calcular trend
    trend = get_trend(stats["recent_accuracy"], ks.historical_accuracy)

    # Atualizar campos
    ks.mastery_score = mastery_data["mastery_score"]
    ks.confidence_score = mastery_data["confidence_score"]
    ks.questions_answered = stats["total"]
    ks.questions_correct = stats["correct"]
    ks.questions_wrong = stats["wrong"]
    ks.recent_accuracy = stats["recent_accuracy"]
    ks.historical_accuracy = stats["accuracy"]
    ks.last_attempt_at = stats["last_attempt_at"]
    ks.consecutive_correct = stats["consecutive_correct"]
    ks.consecutive_wrong = stats["consecutive_wrong"]
    ks.average_response_time = stats["average_response_time"]
    ks.trend = trend
    ks.updated_at = now

    db.session.commit()

    return ks


def update_all_knowledge_states(
    user_id: int,
    now: Optional[datetime] = None,
) -> list[KnowledgeState]:
    """
    Atualiza todos os KnowledgeStates de um usuário.

    Útil para recálculo completo após batch de questões.
    """
    now = now or datetime.now(timezone.utc)

    # Buscar todos os tópicos do usuário que têm questões
    topics_with_questions = (
        db.session.query(Topic.id)
        .filter(Topic.user_id == user_id)
        .join(Question, Question.topic_id == Topic.id)
        .distinct()
        .all()
    )

    topic_ids = [t[0] for t in topics_with_questions]

    updated = []
    for topic_id in topic_ids:
        ks = update_knowledge_state(user_id, topic_id, now)
        updated.append(ks)

    return updated


def get_user_knowledge_summary(user_id: int) -> dict:
    """
    Retorna resumo do estado de conhecimento do usuário.

    Inclui:
    - Média de domínio geral
    - Distribuição por nível
    - Tópicos mais fracos
    - Tópicos mais fortes
    - Tendência geral
    """
    knowledge_states = KnowledgeState.query.filter_by(user_id=user_id).all()

    if not knowledge_states:
        return {
            "average_mastery": 0.0,
            "total_topics": 0,
            "distribution": {
                "expert": 0,
                "proficient": 0,
                "advanced": 0,
                "intermediate": 0,
                "beginner": 0,
            },
            "weakest_topics": [],
            "strongest_topics": [],
            "overall_trend": "stable",
            "has_data": False,
        }

    from app.performance.mastery import get_mastery_level

    # Calcular distribuição
    distribution = {
        "expert": 0,
        "proficient": 0,
        "advanced": 0,
        "intermediate": 0,
        "beginner": 0,
    }

    total_mastery = 0.0
    for ks in knowledge_states:
        level = get_mastery_level(ks.mastery_score)
        distribution[level] += 1
        total_mastery += ks.mastery_score

    average_mastery = _safe_divide(total_mastery, len(knowledge_states))

    # Ordenar por mastery
    sorted_ks = sorted(knowledge_states, key=lambda x: x.mastery_score)

    weakest = sorted_ks[:5]
    strongest = sorted_ks[-5:][::-1]

    # Trend geral
    trends = [ks.trend for ks in knowledge_states]
    improving = trends.count("improving")
    declining = trends.count("declining")

    if improving > declining:
        overall_trend = "improving"
    elif declining > improving:
        overall_trend = "declining"
    else:
        overall_trend = "stable"

    return {
        "average_mastery": round(average_mastery, 2),
        "total_topics": len(knowledge_states),
        "distribution": distribution,
        "weakest_topics": [
            {
                "topic_id": ks.topic_id,
                "subject_id": ks.subject_id,
                "mastery": ks.mastery_score,
                "trend": ks.trend,
            }
            for ks in weakest
        ],
        "strongest_topics": [
            {
                "topic_id": ks.topic_id,
                "subject_id": ks.subject_id,
                "mastery": ks.mastery_score,
                "trend": ks.trend,
            }
            for ks in strongest
        ],
        "overall_trend": overall_trend,
        "has_data": True,
    }


def get_subject_mastery_map(user_id: int) -> dict:
    """
    Retorna mapa de domínio por matéria.

    Útil para o dashboard e para o planner.
    """
    subjects = Subject.query.filter_by(user_id=user_id).all()

    result = {}
    for subject in subjects:
        knowledge_states = KnowledgeState.query.filter_by(
            user_id=user_id, subject_id=subject.id
        ).all()

        if knowledge_states:
            total_mastery = sum(ks.mastery_score for ks in knowledge_states)
            average_mastery = _safe_divide(total_mastery, len(knowledge_states))
            total_questions = sum(ks.questions_answered for ks in knowledge_states)
            total_correct = sum(ks.questions_correct for ks in knowledge_states)
        else:
            average_mastery = 0.0
            total_questions = 0
            total_correct = 0

        result[subject.id] = {
            "subject_id": subject.id,
            "subject_name": subject.nome,
            "subject_cor": subject.cor,
            "area": subject.area,
            "average_mastery": round(average_mastery, 2),
            "total_questions": total_questions,
            "total_correct": total_correct,
            "topics_count": len(knowledge_states),
        }

    return result


def get_topic_detail(
    user_id: int,
    topic_id: int,
) -> Optional[dict]:
    """
    Retorna detalhes completos de um tópico para o dashboard.
    """
    ks = KnowledgeState.query.filter_by(
        user_id=user_id, topic_id=topic_id
    ).first()

    if ks is None:
        return None

    topic = db.session.get(Topic, topic_id)
    subject = db.session.get(Subject, ks.subject_id) if ks.subject_id else None

    return {
        "topic_id": ks.topic_id,
        "topic_name": topic.nome if topic else "",
        "subject_id": ks.subject_id,
        "subject_name": subject.nome if subject else "",
        "subject_cor": subject.cor if subject else "#007bff",
        "mastery_score": ks.mastery_score,
        "confidence_score": ks.confidence_score,
        "questions_answered": ks.questions_answered,
        "questions_correct": ks.questions_correct,
        "questions_wrong": ks.questions_wrong,
        "recent_accuracy": ks.recent_accuracy,
        "historical_accuracy": ks.historical_accuracy,
        "trend": ks.trend,
        "consecutive_correct": ks.consecutive_correct,
        "consecutive_wrong": ks.consecutive_wrong,
        "average_response_time": ks.average_response_time,
        "last_attempt_at": ks.last_attempt_at,
        "last_review_at": ks.last_review_at,
    }


def get_primary_recommendation(
    user_id: int,
    exam_date: Optional[date] = None,
    today: Optional[date] = None,
) -> Optional[dict]:
    """
    Retorna a recomendação principal para o dashboard.

    "O que estudar agora?"
    """
    return recommend_next_topic(user_id, exam_date, today)


def get_secondary_recommendations(
    user_id: int,
    limit: int = 3,
    exam_date: Optional[date] = None,
    today: Optional[date] = None,
) -> list[dict]:
    """
    Retorna recomendações secundárias.
    """
    from app.extensions import db
    from app.models import Subject
    from app.performance.mastery import recommend_study_type
    from app.performance.recommendations import (
        build_reason_messages,
    )

    today = today or date.today()
    now = datetime.now(timezone.utc)

    if exam_date is None:
        exam_date = today + timedelta(days=120)

    days_until_exam = max(0, (exam_date - today).days)

    knowledge_states = KnowledgeState.query.filter_by(user_id=user_id).all()

    if not knowledge_states:
        return []

    candidates = []
    for ks in knowledge_states:
        subject = db.session.get(Subject, ks.subject_id)
        if subject is None:
            continue

        need_data = calculate_need_score(
            mastery_score=ks.mastery_score,
            recent_accuracy=ks.recent_accuracy,
            historical_accuracy=ks.historical_accuracy,
            subject_difficulty=subject.dificuldade,
            days_until_exam=days_until_exam,
            last_review_at=ks.last_review_at,
            confidence_score=ks.confidence_score,
            now=now,
        )

        topic = db.session.get(Topic, ks.topic_id)

        days_since_review = None
        if ks.last_review_at:
            last_rev = ks.last_review_at
            if last_rev.tzinfo is None:
                last_rev = last_rev.replace(tzinfo=timezone.utc)
            days_since_review = (now - last_rev).days

        reason_messages = build_reason_messages(
            need_data["reason_codes"],
            {
                "mastery_score": ks.mastery_score,
                "recent_accuracy": ks.recent_accuracy,
                "recent_total": ks.questions_answered,
                "recent_correct": ks.questions_correct,
                "days_since_review": days_since_review,
                "days_until_exam": days_until_exam,
            },
        )

        candidates.append({
            "topic_id": ks.topic_id,
            "subject_id": ks.subject_id,
            "topic_name": topic.nome if topic else "",
            "subject_name": subject.nome,
            "mastery": ks.mastery_score,
            "need_score": need_data["need_score"],
            "reason_codes": need_data["reason_codes"],
            "reason_messages": reason_messages,
            "recommended_study_type": recommend_study_type(ks.mastery_score),
        })

    candidates.sort(key=lambda x: x["need_score"], reverse=True)

    # Retornar top N, excluindo o primeiro (que é a recomendação principal)
    return candidates[1 : limit + 1]
