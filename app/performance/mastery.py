"""
Mastery Score - PlanejaENEM 3.0.

Calcula o score de domínio (0-100) do aluno por tópico.
Combina múltiplos fatores com pesos centralizados em constantes.

ATENÇÃO: Os pesos são heurísticas determinísticas e podem ser
ajustados posteriormente com base em validação empírica.
Não utilizam IA generativa, LLM ou machine learning.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


# =============================================================================
# PESOS CENTRALIZADOS - HEURÍSTICAS AJUSTÁVEIS
# =============================================================================
# Documentação: Estes pesos são heurísticas e podem ser ajustados
# posteriormente com base em validação empírica.
#
# A soma dos pesos deve ser sempre 1.0 (100%).
# =============================================================================

WEIGHT_ACCURACY = 0.35
WEIGHT_RECENT_PERFORMANCE = 0.20
WEIGHT_DIFFICULTY = 0.15
WEIGHT_CONSISTENCY = 0.10
WEIGHT_RECENCY = 0.10
WEIGHT_CONFIDENCE = 0.10

# Constantes auxiliares
RECENT_WINDOW_SIZE = 10
HIGH_DIFFICULTY_THRESHOLD = 4
LOW_DIFFICULTY_THRESHOLD = 2
MIN_QUESTIONS_FOR_CONFIDENCE = 3
MAX_CONFIDENCE_QUESTIONS = 30
REVIEW_FRESHNESS_DAYS = 7


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divisão segura que retorna default quando denominador é zero."""
    if denominator <= 0:
        return default
    return numerator / denominator


def calculate_accuracy_score(
    questions_correct: int,
    questions_answered: int,
) -> float:
    """
    Calcula o componente de acurácia geral (0-100).

    Baseado no percentual histórico de acertos.
    """
    if questions_answered <= 0:
        return 0.0
    return (_safe_divide(questions_correct, questions_answered)) * 100.0


def calculate_recent_performance_score(
    recent_correct: int,
    recent_total: int,
    historical_accuracy: float,
) -> float:
    """
    Calcula o componente de desempenho recente (0-100).

    Compara a janela recente (últimas N tentativas) com o histórico.
    Se o desempenho recente caiu em relação ao histórico, penaliza.
    Se melhorou, bonifica.
    """
    if recent_total <= 0:
        return historical_accuracy

    recent_accuracy = (_safe_divide(recent_correct, recent_total)) * 100.0

    # Se recente está muito abaixo do histórico, penaliza
    diff = recent_accuracy - historical_accuracy

    if diff <= -20:
        # Queda acentuada: penalização máxima
        return max(0.0, recent_accuracy * 0.6)
    elif diff <= -10:
        # Queda moderada
        return max(0.0, recent_accuracy * 0.8)
    elif diff >= 10:
        # Melhoria: bonificação leve
        return min(100.0, recent_accuracy * 1.1)
    else:
        # Estável: usa desempenho recente
        return recent_accuracy


def calculate_difficulty_score(
    questions_answered: int,
    questions_correct: int,
    average_difficulty: float,
) -> float:
    """
    Calcula o componente de dificuldade (0-100).

    Considera a dificuldade média das questões respondidas.
    80% em questões difíceis vale mais que 80% em questões fáceis.
    """
    if questions_answered <= 0:
        return 0.0

    accuracy = _safe_divide(questions_correct, questions_answered) * 100.0

    # Fator de dificuldade: 1-5 -> 0.0-1.0
    difficulty_factor = max(0.0, min(1.0, (average_difficulty - 1.0) / 4.0))

    # Bônus sutil por dificuldade (não exagerar)
    difficulty_bonus = 1.0 + (difficulty_factor * 0.15)

    score = accuracy * difficulty_bonus
    return min(100.0, max(0.0, score))


def calculate_consistency_score(
    consecutive_correct: int,
    consecutive_wrong: int,
    total_questions: int,
) -> float:
    """
    Calcula o componente de consistência (0-100).

    Um aluno com padrão consistente (90%, 85%, 88%, 91%, 87%)
    é diferente de um com oscilação (100%, 40%, 90%, 35%, 80%).

    Usa acertos/erros consecutivos como proxy de consistência.
    """
    if total_questions <= 0:
        return 0.0

    # Sequência de acertos consecutive
    if consecutive_correct >= 5:
        consistency = 100.0
    elif consecutive_correct >= 3:
        consistency = 80.0
    elif consecutive_correct >= 1:
        consistency = 60.0
    else:
        consistency = 40.0

    # Penalidade por erros consecutive
    if consecutive_wrong >= 3:
        consistency = max(0.0, consistency - 40.0)
    elif consecutive_wrong >= 2:
        consistency = max(0.0, consistency - 25.0)
    elif consecutive_wrong >= 1:
        consistency = max(0.0, consistency - 10.0)

    return consistency


def calculate_recency_score(
    last_attempt_at: Optional[datetime],
    last_review_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> float:
    """
    Calcula o componente de recência (0-100).

    Considera quando foi a última tentativa e a última revisão.
    Atividade recente = score alto.
    Inatividade prolongada = score baixo.
    """
    now = now or datetime.now(timezone.utc)

    if last_attempt_at is None and last_review_at is None:
        return 0.0

    # Última atividade (mais recente entre tentativa e revisão)
    last_activity = last_attempt_at
    if last_review_at and (last_activity is None or last_review_at > last_activity):
        last_activity = last_review_at

    if last_activity is None:
        return 0.0

    # Garantir que last_activity tem timezone
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)

    days_inactive = (now - last_activity).days

    if days_inactive <= 1:
        return 100.0
    elif days_inactive <= 3:
        return 85.0
    elif days_inactive <= 7:
        return 70.0
    elif days_inactive <= 14:
        return 50.0
    elif days_inactive <= 30:
        return 30.0
    else:
        return 10.0


def calculate_confidence_score(
    questions_answered: int,
) -> float:
    """
    Calcula o score de confiança estatística (0-100).

    Evita considerar 1 questão = domínio 90%.
    A confiança aumenta conforme a quantidade de evidências.

    Exemplo:
    - 3 questões → baixa confiança (~30)
    - 10 questões → média confiança (~60)
    - 30+ questões → alta confiança (90+)
    """
    if questions_answered <= 0:
        return 0.0

    # Curva logarítmica suave
    # confidence = 100 * (1 - e^(-k * n))
    # onde k controla a velocidade de convergência
    import math

    k = 0.08
    confidence = 100.0 * (1.0 - math.exp(-k * questions_answered))

    return min(100.0, max(0.0, confidence))


def calculate_mastery(
    questions_correct: int,
    questions_wrong: int,
    questions_answered: int,
    recent_correct: int,
    recent_total: int,
    average_difficulty: float = 3.0,
    consecutive_correct: int = 0,
    consecutive_wrong: int = 0,
    last_attempt_at: Optional[datetime] = None,
    last_review_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> dict:
    """
    Calcula o score de domínio (mastery) do aluno em um tópico.

    Retorna dict com:
    - mastery_score: 0-100
    - confidence_score: 0-100
    - components: dict com cada componente individual
    - weights: dict com os pesos utilizados

    O cálculo combina:
    - 35% acurácia geral
    - 20% desempenho recente
    - 15% dificuldade das questões
    - 10% consistência
    - 10% recência
    - 10% confiança estatística
    """
    now = now or datetime.now(timezone.utc)

    # Calcular acurácia histórica
    historical_accuracy = 0.0
    if questions_answered > 0:
        historical_accuracy = (_safe_divide(questions_correct, questions_answered)) * 100.0

    # Componentes
    accuracy = calculate_accuracy_score(questions_correct, questions_answered)

    recent_perf = calculate_recent_performance_score(
        recent_correct, recent_total, historical_accuracy
    )

    difficulty = calculate_difficulty_score(
        questions_answered, questions_correct, average_difficulty
    )

    consistency = calculate_consistency_score(
        consecutive_correct, consecutive_wrong, questions_answered
    )

    recency = calculate_recency_score(last_attempt_at, last_review_at, now)

    confidence = calculate_confidence_score(questions_answered)

    # Cálculo final ponderado
    mastery = (
        accuracy * WEIGHT_ACCURACY
        + recent_perf * WEIGHT_RECENT_PERFORMANCE
        + difficulty * WEIGHT_DIFFICULTY
        + consistency * WEIGHT_CONSISTENCY
        + recency * WEIGHT_RECENCY
        + confidence * WEIGHT_CONFIDENCE
    )

    # Garantir limites 0-100
    mastery = round(max(0.0, min(100.0, mastery)), 2)
    confidence = round(confidence, 2)

    return {
        "mastery_score": mastery,
        "confidence_score": confidence,
        "components": {
            "accuracy": round(accuracy, 2),
            "recent_performance": round(recent_perf, 2),
            "difficulty": round(difficulty, 2),
            "consistency": round(consistency, 2),
            "recency": round(recency, 2),
            "confidence": round(confidence, 2),
        },
        "weights": {
            "accuracy": WEIGHT_ACCURACY,
            "recent_performance": WEIGHT_RECENT_PERFORMANCE,
            "difficulty": WEIGHT_DIFFICULTY,
            "consistency": WEIGHT_CONSISTENCY,
            "recency": WEIGHT_RECENCY,
            "confidence": WEIGHT_CONFIDENCE,
        },
    }


def get_trend(
    recent_accuracy: Optional[float],
    historical_accuracy: Optional[float],
) -> str:
    """
    Calcula a tendência de desempenho.

    Retorna:
    - 'improving': desempenho recente melhor que histórico
    - 'stable': desempenho estável (diferença < 5%)
    - 'declining': desempenho recente pior que histórico
    """
    if recent_accuracy is None or historical_accuracy is None:
        return "stable"

    diff = recent_accuracy - historical_accuracy

    if diff >= 5:
        return "improving"
    elif diff <= -5:
        return "declining"
    else:
        return "stable"


def get_mastery_level(mastery_score: float) -> str:
    """
    Retorna o nível textual do domínio.

    - 0-39: Iniciante
    - 40-59: Intermediário
    - 60-74: Avançado
    - 75-89: Proficiente
    - 90-100: Expert
    """
    if mastery_score >= 90:
        return "expert"
    elif mastery_score >= 75:
        return "proficient"
    elif mastery_score >= 60:
        return "advanced"
    elif mastery_score >= 40:
        return "intermediate"
    else:
        return "beginner"


def recommend_study_type(mastery_score: float) -> str:
    """
    Recomenda o tipo de estudo baseado no domínio.

    - mastery < 40: teoria + exercícios
    - 40 <= mastery < 60: exercícios
    - 60 <= mastery < 75: questões ENEM
    - 75 <= mastery < 90: questões ENEM + revisão
    - mastery >= 90: questões difíceis + revisão espaçada
    """
    if mastery_score >= 90:
        return "questoes_dificeis_revisao"
    elif mastery_score >= 75:
        return "questoes_enem_revisao"
    elif mastery_score >= 60:
        return "questoes_enem"
    elif mastery_score >= 40:
        return "exercicios"
    else:
        return "teoria_exercicios"
