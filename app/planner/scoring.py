"""
Score inteligente por matéria - PlanejaENEM Adaptive Planner v2.

Calcula a prioridade de estudo de cada matéria com base em múltiplos fatores.
O score é determinístico e não depende de LLM.
"""

from datetime import date, timedelta
from typing import Optional


def normalize(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Normaliza um valor para o intervalo [0, 100]."""
    if max_val <= min_val:
        return 50.0
    clamped = max(min_val, min(max_val, value))
    return ((clamped - min_val) / (max_val - min_val)) * 100.0


def priority_score(priority: int) -> float:
    """
    Contribuição da prioridade definida pelo usuário (1-5).
    Prioridade 5 = 100, prioridade 1 = 20.
    """
    normalized = normalize(priority, 1, 5)
    return normalized


def difficulty_score(difficulty: int) -> float:
    """
    Contribuição da dificuldade (1-5).
    Dificuldade 5 = 100 (mais difícil = mais precisa de estudo).
    """
    normalized = normalize(difficulty, 1, 5)
    return normalized


def performance_score(correct_pct: Optional[float], total_questions: int) -> float:
    """
    Contribuição do desempenho baseado em questões.

    - Se não há dados suficientes (< 3 questões), retorna 50 (neutro).
    - Quanto menor o aproveitamento, maior o score (mais precisa de estudo).
    - Usamos mínimo de 3 questões para evitar conclusões erradas.
    """
    if total_questions < 3 or correct_pct is None:
        return 50.0

    inverted = 100.0 - correct_pct
    return inverted


def exam_proximity_score(days_until_exam: int) -> float:
    """
    Contribuição da proximidade do ENEM.

    - Prova distante (>180 dias): score baixo (30)
    - Prova médio prazo (60-180): score intermediário (50-70)
    - Prova próxima (<60 dias): score alto (80-100)
    - Prova passada: score máximo (100)
    """
    if days_until_exam <= 0:
        return 100.0

    if days_until_exam > 365:
        return 20.0
    elif days_until_exam > 180:
        return 30.0
    elif days_until_exam > 120:
        return 45.0
    elif days_until_exam > 60:
        return 65.0
    elif days_until_exam > 30:
        return 80.0
    elif days_until_exam > 14:
        return 90.0
    elif days_until_exam > 7:
        return 95.0
    else:
        return 100.0


def revision_score(
    last_review_date: Optional[date],
    today: Optional[date] = None,
) -> float:
    """
    Contribuição do tempo desde a última revisão.

    - Sem revisão nunca: score alto (80)
    - Revisão recente: score baixo
    - Revisão atrasada: score alto
    """
    today = today or date.today()

    if last_review_date is None:
        return 80.0

    days_since = (today - last_review_date).days

    if days_since <= 0:
        return 10.0
    elif days_since <= 3:
        return 30.0
    elif days_since <= 7:
        return 50.0
    elif days_since <= 14:
        return 70.0
    elif days_since <= 30:
        return 85.0
    else:
        return 100.0


def overdue_reviews_score(overdue_count: int) -> float:
    """
    Contribuição de revisões atrasadas.
    Mais revisões atrasadas = maior urgência.
    """
    if overdue_count <= 0:
        return 0.0
    elif overdue_count == 1:
        return 40.0
    elif overdue_count == 2:
        return 60.0
    elif overdue_count <= 5:
        return 80.0
    else:
        return 100.0


def pending_tasks_score(pending_count: int, total_tasks: int) -> float:
    """
    Contribuição de tarefas pendentes.
    Proporção de tarefas pendentes em relação ao total.
    """
    if total_tasks <= 0:
        return 50.0

    ratio = pending_count / total_tasks
    return normalize(ratio, 0.0, 1.0)


def calculate_subject_need_score(
    priority: int,
    difficulty: int,
    correct_pct: Optional[float],
    total_questions: int,
    days_until_exam: int,
    last_review_date: Optional[date],
    overdue_reviews: int,
    pending_tasks: int,
    total_tasks: int,
    today: Optional[date] = None,
) -> dict:
    """
    Calcula o score final de necessidade de estudo de uma matéria.

    Retorna um dict com o score total (0-100) e os componentes individuais.
    Pesos calibrados para evitar que um único fator domine:

    - Prioridade: 15%
    - Dificuldade: 15%
    - Desempenho: 20%
    - Proximidade ENEM: 15%
    - Revisão: 10%
    - Revisões atrasadas: 10%
    - Tarefas pendentes: 15%
    """
    today = today or date.today()

    p_score = priority_score(priority)
    d_score = difficulty_score(difficulty)
    perf_score = performance_score(correct_pct, total_questions)
    exam_score = exam_proximity_score(days_until_exam)
    rev_score = revision_score(last_review_date, today)
    overdue_score = overdue_reviews_score(overdue_reviews)
    pending_score = pending_tasks_score(pending_tasks, total_tasks)

    weights = {
        "priority": 0.15,
        "difficulty": 0.15,
        "performance": 0.20,
        "exam_proximity": 0.15,
        "revision": 0.10,
        "overdue_reviews": 0.10,
        "pending_tasks": 0.15,
    }

    total = (
        p_score * weights["priority"]
        + d_score * weights["difficulty"]
        + perf_score * weights["performance"]
        + exam_score * weights["exam_proximity"]
        + rev_score * weights["revision"]
        + overdue_score * weights["overdue_reviews"]
        + pending_score * weights["pending_tasks"]
    )

    total = round(max(0.0, min(100.0, total)), 2)

    return {
        "total": total,
        "components": {
            "priority": round(p_score, 2),
            "difficulty": round(d_score, 2),
            "performance": round(perf_score, 2),
            "exam_proximity": round(exam_score, 2),
            "revision": round(rev_score, 2),
            "overdue_reviews": round(overdue_score, 2),
            "pending_tasks": round(pending_score, 2),
        },
        "weights": weights,
    }
