"""
Recommendation Engine - PlanejaENEM 3.0.

Motor de recomendação determinístico que analisa o estado de conhecimento
do aluno e recomenda o próximo tópico para estudar.

O algoritmo é determinístico: duas execuções com os mesmos dados
devem produzir a mesma recomendação.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional


# =============================================================================
# PESOS DO NEED SCORE - HEURÍSTICAS AJUSTÁVEIS
# =============================================================================
# Documentação: Estes pesos são heurísticas e podem ser ajustados
# posteriormente com base em validação empírica.
# =============================================================================

WEIGHT_LOW_MASTERY = 0.30
WEIGHT_RECENT_POOR = 0.20
WEIGHT_SUBJECT_DIFFICULTY = 0.15
WEIGHT_EXAM_PROXIMITY = 0.15
WEIGHT_OVERDUE_REVIEW = 0.10
WEIGHT_CONFIDENCE = 0.10

# Constantes
HIGH_MASTERY_THRESHOLD = 70
LOW_MASTERY_THRESHOLD = 40
POOR_RECENT_ACCURACY = 50
OVERDUE_REVIEW_DAYS = 7


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divisão segura que retorna default quando denominador é zero."""
    if denominator <= 0:
        return default
    return numerator / denominator


def _calculate_low_mastery_factor(mastery_score: float) -> float:
    """
    Calcula o fator de baixo domínio (0-100).

    Quanto menor o domínio, maior a necessidade.
    """
    if mastery_score <= 0:
        return 100.0
    elif mastery_score >= HIGH_MASTERY_THRESHOLD:
        return 0.0
    else:
        # Interpolação linear inversa
        return 100.0 - mastery_score


def _calculate_recent_poor_factor(
    recent_accuracy: Optional[float],
    historical_accuracy: Optional[float],
) -> float:
    """
    Calcula o fator de desempenho recente ruim (0-100).

    Se o desempenho recente caiu em relação ao histórico, aumenta a necessidade.
    """
    if recent_accuracy is None:
        return 50.0  # Neutro sem dados

    if recent_accuracy < POOR_RECENT_ACCURACY:
        # Desempenho recente já é ruim
        factor = 100.0 - recent_accuracy
    else:
        factor = 0.0

    # Se há queda em relação ao histórico, bônus
    if historical_accuracy is not None and recent_accuracy < historical_accuracy:
        drop = historical_accuracy - recent_accuracy
        factor = min(100.0, factor + drop)

    return factor


def _calculate_subject_difficulty_factor(subject_difficulty: int) -> float:
    """
    Calcula o fator de dificuldade da matéria (0-100).

    Matérias mais difíceis têm prioridade levemente maior.
    """
    # Dificuldade 1-5 -> 0-100
    return max(0.0, min(100.0, ((subject_difficulty - 1) / 4.0) * 100.0))


def _calculate_exam_proximity_factor(days_until_exam: int) -> float:
    """
    Calcula o fator de proximidade do ENEM (0-100).

    Prova próxima = maior urgência.
    """
    if days_until_exam <= 0:
        return 100.0
    elif days_until_exam <= 14:
        return 95.0
    elif days_until_exam <= 30:
        return 85.0
    elif days_until_exam <= 60:
        return 70.0
    elif days_until_exam <= 120:
        return 50.0
    elif days_until_exam <= 180:
        return 35.0
    else:
        return 20.0


def _calculate_overdue_review_factor(
    last_review_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> float:
    """
    Calcula o fator de revisão atrasada (0-100).

    Se a última revisão foi há muito tempo, aumenta a necessidade.
    """
    now = now or datetime.now(timezone.utc)

    if last_review_at is None:
        return 80.0  # Nunca revisou

    if last_review_at.tzinfo is None:
        last_review_at = last_review_at.replace(tzinfo=timezone.utc)

    days_since_review = (now - last_review_at).days

    if days_since_review <= 3:
        return 10.0
    elif days_since_review <= 7:
        return 30.0
    elif days_since_review <= 14:
        return 60.0
    elif days_since_review <= 30:
        return 80.0
    else:
        return 100.0


def _calculate_confidence_factor(confidence_score: float) -> float:
    """
    Calcula o fator de confiança (0-100).

    Se a confiança é baixa, o tópico precisa de mais prática.
    """
    # Inverso: baixa confiança = alta necessidade
    return 100.0 - confidence_score


def calculate_need_score(
    mastery_score: float,
    recent_accuracy: Optional[float],
    historical_accuracy: Optional[float],
    subject_difficulty: int,
    days_until_exam: int,
    last_review_at: Optional[datetime],
    confidence_score: float,
    now: Optional[datetime] = None,
) -> dict:
    """
    Calcula o score de necessidade (need score) de um tópico.

    Retorna dict com:
    - need_score: 0-100 (maior = mais precisa de estudo)
    - reason_codes: lista de códigos de motivo
    - components: dict com cada componente individual
    """
    now = now or datetime.now(timezone.utc)

    low_mastery = _calculate_low_mastery_factor(mastery_score)
    recent_poor = _calculate_recent_poor_factor(recent_accuracy, historical_accuracy)
    subject_diff = _calculate_subject_difficulty_factor(subject_difficulty)
    exam_prox = _calculate_exam_proximity_factor(days_until_exam)
    overdue_rev = _calculate_overdue_review_factor(last_review_at, now)
    confidence = _calculate_confidence_factor(confidence_score)

    # Cálculo ponderado
    need = (
        low_mastery * WEIGHT_LOW_MASTERY
        + recent_poor * WEIGHT_RECENT_POOR
        + subject_diff * WEIGHT_SUBJECT_DIFFICULTY
        + exam_prox * WEIGHT_EXAM_PROXIMITY
        + overdue_rev * WEIGHT_OVERDUE_REVIEW
        + confidence * WEIGHT_CONFIDENCE
    )

    need = round(max(0.0, min(100.0, need)), 2)

    # Gerar reason codes
    reason_codes = []

    if mastery_score < LOW_MASTERY_THRESHOLD:
        reason_codes.append("low_mastery")
    elif mastery_score < HIGH_MASTERY_THRESHOLD:
        reason_codes.append("moderate_mastery")

    if recent_accuracy is not None and recent_accuracy < POOR_RECENT_ACCURACY:
        reason_codes.append("recent_poor_performance")

    if recent_accuracy is not None and historical_accuracy is not None:
        if recent_accuracy < historical_accuracy - 10:
            reason_codes.append("performance_declining")

    if overdue_rev >= 60:
        reason_codes.append("overdue_review")

    if confidence_score < 40:
        reason_codes.append("low_confidence")

    if exam_prox >= 85:
        reason_codes.append("exam_approaching")

    return {
        "need_score": need,
        "reason_codes": reason_codes,
        "components": {
            "low_mastery": round(low_mastery, 2),
            "recent_poor": round(recent_poor, 2),
            "subject_difficulty": round(subject_diff, 2),
            "exam_proximity": round(exam_prox, 2),
            "overdue_review": round(overdue_rev, 2),
            "confidence": round(confidence, 2),
        },
        "weights": {
            "low_mastery": WEIGHT_LOW_MASTERY,
            "recent_poor": WEIGHT_RECENT_POOR,
            "subject_difficulty": WEIGHT_SUBJECT_DIFFICULTY,
            "exam_proximity": WEIGHT_EXAM_PROXIMITY,
            "overdue_review": WEIGHT_OVERDUE_REVIEW,
            "confidence": WEIGHT_CONFIDENCE,
        },
    }


def build_reason_messages(reason_codes: list[str], context: dict) -> list[str]:
    """
    Converte reason codes em mensagens legíveis para o usuário.

    Retorna lista de strings explicando por que o tópico foi recomendado.
    """
    messages = []

    if "low_mastery" in reason_codes:
        mastery = context.get("mastery_score", 0)
        messages.append(f"Seu domínio estimado é {mastery:.0f}%")

    if "moderate_mastery" in reason_codes:
        mastery = context.get("mastery_score", 0)
        messages.append(f"Seu domínio é {mastery:.0f}%, mas pode melhorar")

    if "recent_poor_performance" in reason_codes:
        recent = context.get("recent_accuracy")
        if recent is not None:
            total_recent = context.get("recent_total", 0)
            correct_recent = context.get("recent_correct", 0)
            messages.append(
                f"Você acertou {correct_recent} de {total_recent} questões recentes"
            )

    if "performance_declining" in reason_codes:
        messages.append("Você apresenta queda recente de desempenho")

    if "overdue_review" in reason_codes:
        days = context.get("days_since_review")
        if days is not None:
            messages.append(f"Sua última revisão foi há {days} dias")
        else:
            messages.append("Você nunca revisou este conteúdo")

    if "low_confidence" in reason_codes:
        messages.append("Ainda há poucos dados para avaliar seu domínio")

    if "exam_approaching" in reason_codes:
        days = context.get("days_until_exam")
        if days is not None:
            messages.append(f"O ENEM está em {days} dias")

    return messages


def recommend_next_topic(
    user_id: int,
    exam_date: Optional[date] = None,
    today: Optional[date] = None,
) -> Optional[dict]:
    """
    Recomenda o próximo tópico para o aluno estudar.

    Analisa todos os tópico do aluno e escolhe o melhor candidato
    baseado no score de necessidade.

    Retorna dict com:
    - topic_id
    - subject_id
    - mastery
    - need_score
    - reason_codes
    - reason_messages
    - recommended_study_type

    Ou None se não houver tópicos disponíveis.
    """
    from app.extensions import db
    from app.models import Subject, Topic
    from app.performance.models import KnowledgeState
    from app.performance.mastery import recommend_study_type

    today = today or date.today()
    now = datetime.now(timezone.utc)

    if exam_date is None:
        exam_date = today + timedelta(days=120)

    days_until_exam = max(0, (exam_date - today).days)

    # Buscar todos os KnowledgeStates do usuário
    knowledge_states = KnowledgeState.query.filter_by(user_id=user_id).all()

    if not knowledge_states:
        # Se não há KnowledgeStates, buscar tópicos sem estado
        topics = (
            Topic.query.filter_by(user_id=user_id)
            .join(Subject)
            .all()
        )

        if not topics:
            return None

        # Para tópicos sem estado, criar recomendação inicial
        best_topic = topics[0]
        return {
            "topic_id": best_topic.id,
            "subject_id": best_topic.subject_id,
            "topic_name": best_topic.nome,
            "subject_name": best_topic.subject.nome if best_topic.subject else "",
            "mastery": 0,
            "need_score": 80.0,
            "reason_codes": ["no_data", "needs_initial_assessment"],
            "reason_messages": [
                "Este tópico ainda não possui dados suficientes",
                "Recomendamos começar com questões para avaliar seu domínio",
            ],
            "recommended_study_type": "teoria_exercicios",
        }

    # Calcular need score para cada KnowledgeState
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
        topic_name = topic.nome if topic else ""

        # Contexto para mensagens
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
            "topic_name": topic_name,
            "subject_name": subject.nome,
            "mastery": ks.mastery_score,
            "need_score": need_data["need_score"],
            "reason_codes": need_data["reason_codes"],
            "reason_messages": reason_messages,
            "recommended_study_type": recommend_study_type(ks.mastery_score),
            "confidence_score": ks.confidence_score,
        })

    if not candidates:
        return None

    # Ordenar por need_score (maior = mais urgente)
    candidates.sort(key=lambda x: x["need_score"], reverse=True)

    # Em caso de empate, preferir:
    # 1. Menor confiança (mais dados para coletar)
    # 2. Menor domínio
    best = candidates[0]
    for candidate in candidates[1:]:
        if candidate["need_score"] == best["need_score"]:
            if candidate["confidence_score"] < best["confidence_score"]:
                best = candidate
            elif (
                candidate["confidence_score"] == best["confidence_score"]
                and candidate["mastery"] < best["mastery"]
            ):
                best = candidate

    return best
