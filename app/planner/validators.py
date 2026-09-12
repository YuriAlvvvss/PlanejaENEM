"""
Validadores do planner - PlanejaENEM Adaptive Planner v2.

Valida entradas e tratamento de casos extremos.
"""

from datetime import date, datetime, timedelta
from typing import Optional

DAYS_ORDER = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]

DAY_ALIASES = {
    "mon": "seg",
    "tue": "ter",
    "wed": "qua",
    "thu": "qui",
    "fri": "sex",
    "sat": "sab",
    "sun": "dom",
}

MIN_DAILY_MINUTES = 30
MAX_DAILY_MINUTES = 600
MIN_SUBJECTS = 1
MAX_SUBJECTS = 20
MIN_EXAM_DAYS_AHEAD = 1
MAX_EXAM_DAYS_AHEAD = 730


def validate_available_days(days: list) -> tuple[list, list[str]]:
    """
    Valida e normaliza os dias disponíveis.

    Retorna (dias_validos, erros).
    """
    if not days:
        return [], ["Selecione pelo menos um dia da semana."]

    normalized = []
    errors = []
    seen = set()

    for day in days:
        day_str = str(day).strip().lower()
        alias = DAY_ALIASES.get(day_str, day_str)
        if alias in DAYS_ORDER and alias not in seen:
            normalized.append(alias)
            seen.add(alias)

    if not normalized:
        errors.append("Nenhum dia válido selecionado.")

    return normalized, errors


def validate_available_hours(hours_str: str) -> tuple[list[str], list[str]]:
    """
    Valida e normaliza os horários disponíveis.

    Formato esperado: "08:00-10:00, 15:00-17:00"

    Retorna (horarios_validos, erros).
    """
    if not hours_str or not str(hours_str).strip():
        return [], ["Informe os horários disponíveis."]

    errors = []
    parsed_slots = []

    for chunk in str(hours_str).split(","):
        slot = chunk.strip()
        if not slot:
            continue

        if "-" not in slot:
            errors.append(f"Formato inválido: '{slot}'. Use HH:MM-HH:MM.")
            continue

        parts = slot.split("-")
        if len(parts) != 2:
            errors.append(f"Formato inválido: '{slot}'. Use HH:MM-HH:MM.")
            continue

        try:
            start = datetime.strptime(parts[0].strip(), "%H:%M").time()
            end = datetime.strptime(parts[1].strip(), "%H:%M").time()

            if end <= start:
                errors.append(f"Horário final ({parts[1].strip()}) deve ser após o inicial ({parts[0].strip()}).")
                continue

            slot_minutes = int(
                (datetime.combine(date.today(), end) -
                 datetime.combine(date.today(), start)).total_seconds() / 60
            )
            if slot_minutes < 30:
                errors.append(f"Slot '{slot}' muito curto (mínimo 30 minutos).")
                continue

            parsed_slots.append((start, end))
        except ValueError:
            errors.append(f"Horário inválido: '{slot}'. Use formato HH:MM.")

    parsed_slots.sort()
    valid_slots = []
    previous_end = None
    for start, end in parsed_slots:
        if previous_end is not None and start < previous_end:
            errors.append("Os horários disponíveis não podem se sobrepor.")
            continue
        valid_slots.append(f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}")
        previous_end = end

    return valid_slots, errors


def validate_daily_minutes(minutes) -> tuple[int, list[str]]:
    """
    Valida o tempo diário de estudo.

    Retorna (minutos_validos, erros).
    """
    errors = []

    try:
        minutes = int(minutes)
    except (ValueError, TypeError):
        errors.append("Tempo diário deve ser um número.")
        return MIN_DAILY_MINUTES, errors

    if minutes < MIN_DAILY_MINUTES:
        errors.append(f"Tempo diário mínimo é {MIN_DAILY_MINUTES} minutos.")
        return MIN_DAILY_MINUTES, errors

    if minutes > MAX_DAILY_MINUTES:
        errors.append(f"Tempo diário máximo é {MAX_DAILY_MINUTES} minutos.")
        return MAX_DAILY_MINUTES, errors

    return minutes, errors


def validate_exam_date(exam_date_str: str, today: Optional[date] = None) -> tuple[Optional[date], list[str]]:
    """
    Valida a data da prova.

    Retorna (data_valida, erros).
    """
    today = today or date.today()
    errors = []

    if not exam_date_str:
        return None, ["Informe a data da prova."]

    try:
        exam_date = datetime.strptime(str(exam_date_str), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None, ["Formato de data inválido. Use AAAA-MM-DD."]

    days_until = (exam_date - today).days

    if days_until < 0:
        errors.append("A data da prova já passou. O cronograma será gerado até hoje.")
        return today, errors

    if days_until == 0:
        errors.append("A prova é hoje! O sistema gerará um plano mínimo.")

    if days_until > MAX_EXAM_DAYS_AHEAD:
        errors.append(f"A data está muito distante (mais de {MAX_EXAM_DAYS_AHEAD} dias).")

    return exam_date, errors


def validate_subject_settings(
    subjects: list,
    form_data: dict,
) -> tuple[dict, list[str]]:
    """
    Mantem compatibilidade com o planner antigo sem aceitar preferencias manuais.

    Retorna (settings_validos, erros).
    """
    return {}, []


def check_availability_conflict(
    new_start: str,
    new_end: str,
    existing_sessions: list[dict],
    target_date: date,
) -> bool:
    """
    Verifica se há conflito de horário com sessões existentes.

    Retorna True se houver conflito.
    """
    from datetime import datetime

    try:
        new_s = datetime.strptime(new_start, "%H:%M").time()
        new_e = datetime.strptime(new_end, "%H:%M").time()
    except (ValueError, TypeError):
        return True

    for session in existing_sessions:
        if session.get("session_date") != target_date:
            continue

        try:
            exist_s = session.get("start_time")
            exist_e = session.get("end_time")

            if isinstance(exist_s, str):
                exist_s = datetime.strptime(exist_s, "%H:%M").time()
            if isinstance(exist_e, str):
                exist_e = datetime.strptime(exist_e, "%H:%M").time()

            if new_s < exist_e and new_e > exist_s:
                return True
        except (ValueError, TypeError):
            continue

    return False


def validate_total_sessions_per_day(
    sessions_count: int,
    max_per_day: int = 6,
) -> list[str]:
    """Valida se não excedemos o limite de sessões por dia."""
    if sessions_count > max_per_day:
        return [f"Muitas sessões em um dia ({sessions_count}). Máximo recomendado: {max_per_day}."]
    return []


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divisão segura que evita divisão por zero."""
    if denominator <= 0:
        return default
    return numerator / denominator
