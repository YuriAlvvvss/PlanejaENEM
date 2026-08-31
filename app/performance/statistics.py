"""
Performance statistics services for PlanejaENEM.

Computes accuracy, subject-level breakdown, difficulty breakdown,
and recent performance trends from QuestionAttempt data.
"""

from collections import defaultdict
from typing import Optional

from app.models import Question, QuestionAttempt, Subject, Topic


def get_overall_stats(user_id: int) -> dict:
    total = QuestionAttempt.query.filter_by(user_id=user_id).count()
    correct = QuestionAttempt.query.filter_by(user_id=user_id, correta=True).count()
    wrong = total - correct
    accuracy = round((correct / total) * 100) if total > 0 else 0

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy,
    }


def get_subject_stats(user_id: int) -> list[dict]:
    subjects = Subject.query.filter_by(user_id=user_id).order_by(Subject.nome).all()
    result = []
    for subject in subjects:
        questions = Question.query.filter_by(user_id=user_id, subject_id=subject.id).all()
        question_ids = [q.id for q in questions]
        if not question_ids:
            continue

        total = QuestionAttempt.query.filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
        ).count()
        correct = QuestionAttempt.query.filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
            QuestionAttempt.correta == True,
        ).count()
        wrong = total - correct
        accuracy = round((correct / total) * 100) if total > 0 else 0

        result.append({
            "subject_id": subject.id,
            "subject_nome": subject.nome,
            "subject_cor": subject.cor,
            "total": total,
            "correct": correct,
            "wrong": wrong,
            "accuracy": accuracy,
        })

    return sorted(result, key=lambda x: x["accuracy"], reverse=True)


def get_topic_stats(user_id: int, subject_id: Optional[int] = None) -> list[dict]:
    query = Topic.query.filter_by(user_id=user_id)
    if subject_id is not None:
        query = query.filter_by(subject_id=subject_id)
    topics = query.order_by(Topic.nome).all()

    result = []
    for topic in topics:
        questions = Question.query.filter_by(user_id=user_id, topic_id=topic.id).all()
        question_ids = [q.id for q in questions]
        if not question_ids:
            continue

        total = QuestionAttempt.query.filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
        ).count()
        correct = QuestionAttempt.query.filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
            QuestionAttempt.correta == True,
        ).count()
        wrong = total - correct
        accuracy = round((correct / total) * 100) if total > 0 else 0

        result.append({
            "topic_id": topic.id,
            "topic_nome": topic.nome,
            "subject_nome": topic.subject.nome if topic.subject else "",
            "total": total,
            "correct": correct,
            "wrong": wrong,
            "accuracy": accuracy,
        })

    return sorted(result, key=lambda x: x["accuracy"], reverse=True)


def get_difficulty_stats(user_id: int) -> list[dict]:
    questions = Question.query.filter_by(user_id=user_id).all()
    question_ids = [q.id for q in questions]
    if not question_ids:
        return []

    attempts = QuestionAttempt.query.filter(
        QuestionAttempt.user_id == user_id,
        QuestionAttempt.question_id.in_(question_ids),
    ).all()

    question_map = {q.id: q for q in questions}

    difficulty_data = defaultdict(lambda: {"total": 0, "correct": 0})
    for attempt in attempts:
        q = question_map.get(attempt.question_id)
        if q:
            d = q.dificuldade
            difficulty_data[d]["total"] += 1
            if attempt.correta:
                difficulty_data[d]["correct"] += 1

    result = []
    for diff in sorted(difficulty_data.keys()):
        data = difficulty_data[diff]
        wrong = data["total"] - data["correct"]
        accuracy = round((data["correct"] / data["total"]) * 100) if data["total"] > 0 else 0
        result.append({
            "dificuldade": diff,
            "total": data["total"],
            "correct": data["correct"],
            "wrong": wrong,
            "accuracy": accuracy,
        })

    return result


def get_recent_performance(user_id: int, limit: int = 20) -> dict:
    attempts = (
        QuestionAttempt.query.filter_by(user_id=user_id)
        .order_by(QuestionAttempt.attempted_at.desc())
        .limit(limit)
        .all()
    )

    if not attempts:
        return {
            "recent_accuracy": 0,
            "recent_total": 0,
            "recent_correct": 0,
            "attempts": [],
        }

    recent_correct = sum(1 for a in attempts if a.correta)
    recent_total = len(attempts)
    recent_accuracy = round((recent_correct / recent_total) * 100) if recent_total > 0 else 0

    enriched = []
    for attempt in attempts:
        q = attempt.question
        enriched.append({
            "attempted_at": attempt.attempted_at,
            "correta": attempt.correta,
            "resposta": attempt.resposta,
            "correct_answer": q.resposta_correta if q else "?",
            "subject_nome": q.subject.nome if q and q.subject else "",
            "dificuldade": q.dificuldade if q else 0,
            "tempo_segundos": attempt.tempo_segundos,
        })

    return {
        "recent_accuracy": recent_accuracy,
        "recent_total": recent_total,
        "recent_correct": recent_correct,
        "attempts": enriched,
    }


def get_best_worst_subject(user_id: int) -> tuple[Optional[dict], Optional[dict]]:
    stats = get_subject_stats(user_id)
    if not stats:
        return None, None
    best = stats[0]
    worst = stats[-1]
    return best, worst


def get_area_stats(user_id: int) -> list[dict]:
    subjects = Subject.query.filter_by(user_id=user_id).all()
    from app.areas import AREA_LABELS

    area_data = defaultdict(lambda: {"total": 0, "correct": 0, "subjects": 0})

    for subject in subjects:
        questions = Question.query.filter_by(user_id=user_id, subject_id=subject.id).all()
        question_ids = [q.id for q in questions]
        if not question_ids:
            continue

        total = QuestionAttempt.query.filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
        ).count()
        correct = QuestionAttempt.query.filter(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(question_ids),
            QuestionAttempt.correta == True,
        ).count()

        area = subject.area or "outro"
        area_data[area]["total"] += total
        area_data[area]["correct"] += correct
        area_data[area]["subjects"] += 1

    result = []
    for area_key, data in area_data.items():
        if data["total"] == 0:
            continue
        accuracy = round((data["correct"] / data["total"]) * 100) if data["total"] > 0 else 0
        result.append({
            "area_key": area_key,
            "area_label": AREA_LABELS.get(area_key, area_key),
            "total": data["total"],
            "correct": data["correct"],
            "wrong": data["total"] - data["correct"],
            "accuracy": accuracy,
        })

    return sorted(result, key=lambda x: x["accuracy"], reverse=True)
