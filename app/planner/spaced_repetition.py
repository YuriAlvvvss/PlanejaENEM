"""
Revisão espaçada adaptativa - PlanejaENEM Adaptive Planner v2.

Calcula a próxima data de revisão com base no desempenho do aluno.
Quanto melhor o desempenho, maior o intervalo entre revisões.
"""

from datetime import date, timedelta
from typing import Optional


REVIEW_INTERVALS = {
    "excellent": 30,
    "good": 14,
    "medium": 7,
    "low": 3,
    "very_low": 1,
}


def classify_performance(
    correct_pct: Optional[float],
    total_questions: int,
    min_questions: int = 3,
) -> str:
    """
    Classifica o desempenho do aluno em uma matéria.

    Retorna: excellent, good, medium, low, very_low
    Se não houver dados suficientes, retorna 'medium' (neutro).
    """
    if total_questions < min_questions or correct_pct is None:
        return "medium"

    if correct_pct >= 85:
        return "excellent"
    elif correct_pct >= 70:
        return "good"
    elif correct_pct >= 50:
        return "medium"
    elif correct_pct >= 30:
        return "low"
    else:
        return "very_low"


def get_review_interval(performance: str) -> int:
    """
    Retorna o intervalo de dias para a próxima revisão
    baseado na classificação de desempenho.
    """
    return REVIEW_INTERVALS.get(performance, 7)


def calculate_next_review_date(
    correct_pct: Optional[float],
    total_questions: int,
    today: Optional[date] = None,
    review_count: int = 0,
    min_questions: int = 3,
) -> Optional[date]:
    """
    Calcula a próxima data de revisão.

    Lógica:
    - excellent (>=85%): 30 dias
    - good (>=70%): 14 dias
    - medium (>=50%): 7 dias
    - low (>=30%): 3 dias
    - very_low (<30%): 1 dia

    Se não houver dados suficientes (< min_questions), usa intervalo padrão de 7 dias.

    O review_count permite ajustar levemente: revisões subsequentes podem
    ter intervalos crescentes se o desempenho se mantiver bom.
    """
    today = today or date.today()

    performance = classify_performance(correct_pct, total_questions, min_questions)
    base_interval = get_review_interval(performance)

    if review_count > 0 and performance in ("excellent", "good"):
        multiplier = min(1.5, 1.0 + (review_count * 0.1))
        base_interval = int(base_interval * multiplier)

    return today + timedelta(days=base_interval)


def calculate_next_review_from_task(
    task_completed: bool,
    correct_pct: Optional[float] = None,
    total_questions: int = 0,
    today: Optional[date] = None,
    existing_review_date: Optional[date] = None,
    review_count: int = 0,
) -> Optional[date]:
    """
    Calcula a próxima data de revisão para uma tarefa.

    Usado quando uma tarefa é concluída ou quando o aluno marca
    uma questão como correta/errada.
    """
    if not task_completed:
        return None

    return calculate_next_review_date(
        correct_pct=correct_pct,
        total_questions=total_questions,
        today=today,
        review_count=review_count,
    )


def get_review_status(
    review_date: Optional[date],
    today: Optional[date] = None,
) -> str:
    """
    Retorna o status de uma revisão:
    - 'overdue': revisão atrasada (data anterior a hoje)
    - 'today': revisão para hoje
    - 'upcoming': revisão futura
    - 'none': sem revisão agendada
    """
    if review_date is None:
        return "none"

    today = today or date.today()

    if review_date < today:
        return "overdue"
    elif review_date == today:
        return "today"
    else:
        return "upcoming"


def calculate_overdue_days(
    review_date: Optional[date],
    today: Optional[date] = None,
) -> int:
    """
    Retorna quantos dias uma revisão está atrasada.
    Retorna 0 se não estiver atrasada.
    """
    if review_date is None:
        return 0

    today = today or date.today()
    delta = (today - review_date).days

    return max(0, delta)


def adaptive_interval_adjustment(
    base_interval: int,
    consecutive_good: int,
    consecutive_bad: int,
) -> int:
    """
    Ajusta o intervalo de revisão baseado em padrões de desempenho.

    - Se o aluno está acertando consistentemente, aumenta o intervalo.
    - Se o aluno está errando consistentemente, diminui o intervalo.
    """
    adjusted = base_interval

    if consecutive_good >= 3:
        adjusted = int(base_interval * min(2.0, 1.0 + consecutive_good * 0.15))
    elif consecutive_bad >= 2:
        adjusted = max(1, int(base_interval * 0.5))

    return max(1, adjusted)
