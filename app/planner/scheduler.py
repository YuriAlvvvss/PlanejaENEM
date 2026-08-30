"""
Scheduler adaptativo - PlanejaENEM Adaptive Planner v2.

Distribui sessões de estudo respeitando:
- Balanceamento entre matérias
- Limite de sessões consecutivas
- Disponibilidade semanal
- Metas adaptativas
- Tipos de estudo
"""

from datetime import date, datetime, time, timedelta
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

STUDY_TYPES = ["teoria", "exercicios", "questoes_enem", "revisao", "simulado"]


def get_study_phase(days_until_exam: int) -> str:
    """
    Determina a fase de estudo baseada na proximidade da prova.

    - 'long_term': >120 dias (foco em teoria e base)
    - 'medium_term': 30-120 dias (teoria + exercícios + revisão)
    - 'final_stretch': <30 dias (questões, revisão, simulados)
    """
    if days_until_exam > 120:
        return "long_term"
    elif days_until_exam > 30:
        return "medium_term"
    else:
        return "final_stretch"


def recommend_study_type(
    phase: str,
    performance_level: str,
    days_until_exam: int,
) -> str:
    """
    Recomenda o tipo de estudo baseado na fase e desempenho.

    Fases:
    - long_term: foco em teoria e construção de base
    - medium_term: equilíbrio entre teoria, exercícios e revisão
    - final_stretch: foco em questões, revisão e simulados

    Desempenho:
    - very_low/low: teoria + exercícios
    - medium: exercícios + questões ENEM
    - good/excellent: questões + revisão
    """
    if phase == "long_term":
        if performance_level in ("very_low", "low"):
            return "teoria"
        elif performance_level == "medium":
            return "exercicios"
        else:
            return "exercicios"

    elif phase == "medium_term":
        if performance_level in ("very_low", "low"):
            return "teoria"
        elif performance_level == "medium":
            return "exercicios"
        elif performance_level == "good":
            return "questoes_enem"
        else:
            return "revisao"

    else:  # final_stretch
        if performance_level in ("very_low", "low"):
            return "exercicios"
        elif performance_level == "medium":
            return "questoes_enem"
        else:
            return "questoes_enem"


def calculate_time_allocation(
    subject_scores: list[dict],
    weekly_goal_minutes: int,
    available_days: int,
) -> dict:
    """
    Distribui o tempo semanal de acordo com a necessidade de cada matéria.

    subject_scores: lista de dicts com 'subject_id', 'score', 'area'
    weekly_goal_minutes: meta semanal total
    available_days: número de dias disponíveis por semana

    Retorna dict com alocação por matéria e motivo.
    """
    if not subject_scores or weekly_goal_minutes <= 0:
        return {"allocations": {}, "total_minutes": 0}

    total_score = sum(s["score"] for s in subject_scores)
    if total_score <= 0:
        equal_minutes = weekly_goal_minutes // len(subject_scores)
        allocations = {}
        for s in subject_scores:
            allocations[s["subject_id"]] = {
                "minutes": equal_minutes,
                "reason": "Distribuição igualitária (scores zero)",
            }
        return {"allocations": allocations, "total_minutes": weekly_goal_minutes}

    allocations = {}
    distributed = 0

    sorted_subjects = sorted(subject_scores, key=lambda x: x["score"], reverse=True)

    for i, subject in enumerate(sorted_subjects):
        proportion = subject["score"] / total_score
        allocated = int(weekly_goal_minutes * proportion)

        min_minutes = 30
        allocated = max(min_minutes, allocated)

        if i == len(sorted_subjects) - 1:
            allocated = weekly_goal_minutes - distributed

        allocations[subject["subject_id"]] = {
            "minutes": max(0, allocated),
            "proportion": round(proportion * 100, 1),
            "reason": f"Score: {subject['score']:.1f} ({proportion*100:.1f}%)",
        }
        distributed += allocated

    return {"allocations": allocations, "total_minutes": distributed}


def should_limit_consecutive(
    recent_subjects: list[int],
    max_consecutive: int = 3,
) -> bool:
    """
    Verifica se deve limitar sessões consecutivas da mesma matéria.

    Retorna True se a mesma matéria já apareceu max_consecutive vezes seguidas.
    """
    if not recent_subjects or max_consecutive <= 0:
        return False

    last_n = recent_subjects[-max_consecutive:]
    return len(set(last_n)) == 1 and len(last_n) == max_consecutive


def pick_next_subject(
    subject_scores: list[dict],
    recent_subjects: list[int],
    area_balance: dict,
    max_consecutive: int = 2,
) -> Optional[dict]:
    """
    Seleciona a próxima matéria para estudar.

    Considera:
    - Score de necessidade (maior = mais urgente)
    - Limite de sessões consecutivas
    - Balanceamento entre áreas do ENEM

    Retorna o dict da matéria selecionada ou None.
    """
    if not subject_scores:
        return None

    available = list(subject_scores)

    if should_limit_consecutive(recent_subjects, max_consecutive):
        last_subject = recent_subjects[-1]
        filtered = [s for s in available if s["subject_id"] != last_subject]
        if filtered:
            available = filtered

    area_counts = {}
    for subject_id in recent_subjects[-7:]:
        for s in subject_scores:
            if s["subject_id"] == subject_id:
                area = s.get("area", "outro")
                area_counts[area] = area_counts.get(area, 0) + 1

    max_area_count = max(area_counts.values()) if area_counts else 0

    def sort_key(s):
        area = s.get("area", "outro")
        area_penalty = 0
        if area_counts.get(area, 0) >= max_area_count and max_area_count > 0:
            area_penalty = -10

        return (area_penalty, -s["score"])

    available.sort(key=sort_key)

    return available[0] if available else None


def generate_session_schedule(
    available_days: list[str],
    available_hours: list[str],
    daily_minutes: int,
    exam_date: date,
    today: Optional[date] = None,
) -> list[dict]:
    """
    Gera a grade de horários disponível entre hoje e a data da prova.

    Retorna lista de dicts com:
    - date: data
    - day_of_week: dia da semana
    - slots: lista de slots (start_time, end_time)
    """
    today = today or date.today()
    schedule = []

    day_aliases_rev = {v: k for k, v in DAY_ALIASES.items()}
    selected_weekdays = set()
    for day in available_days:
        normalized = DAY_ALIASES.get(day, day).lower()
        if normalized in DAYS_ORDER:
            idx = DAYS_ORDER.index(normalized)
            selected_weekdays.add(idx)

    if not selected_weekdays:
        return []

    slots = []
    for hour_range in available_hours:
        parts = hour_range.split("-")
        if len(parts) != 2:
            continue
        try:
            start = datetime.strptime(parts[0].strip(), "%H:%M").time()
            end = datetime.strptime(parts[1].strip(), "%H:%M").time()
            if end > start:
                slots.append((start, end))
        except ValueError:
            continue

    if not slots:
        return []

    current_date = today
    while current_date <= exam_date:
        if current_date.weekday() in selected_weekdays:
            schedule.append({
                "date": current_date,
                "day_of_week": current_date.strftime("%a").lower()[:3],
                "slots": slots,
            })
        current_date += timedelta(days=1)

    return schedule


def distribute_sessions(
    schedule: list[dict],
    subject_allocations: dict,
    subject_data: dict,
    daily_minutes: int,
    study_types: Optional[list[str]] = None,
) -> list[dict]:
    """
    Distribui sessões de estudo na grade de horários.

    schedule: grade de horários
    subject_allocations: dict {subject_id: {"minutes": X}}
    subject_data: dict {subject_id: {"score": X, "area": Y, "performance": Z}}
    daily_minutes: limite diário

    Retorna lista de sessões geradas.
    """
    if not schedule or not subject_allocations:
        return []

    sessions = []
    minutes_used_today = 0
    current_date = None
    recent_subjects = []

    weekly_minutes = {}
    for subject_id, alloc in subject_allocations.items():
        weekly_minutes[subject_id] = alloc.get("minutes", 0)

    weekly_used = {sid: 0 for sid in subject_allocations}

    for day_info in schedule:
        day_date = day_info["date"]
        if day_date != current_date:
            current_date = day_date
            minutes_used_today = 0

        for slot_start, slot_end in day_info["slots"]:
            slot_minutes = int(
                (datetime.combine(date.today(), slot_end) -
                 datetime.combine(date.today(), slot_start)).total_seconds() / 60
            )

            remaining_daily = daily_minutes - minutes_used_today
            available_minutes = min(slot_minutes, remaining_daily)

            if available_minutes <= 0:
                continue

            subject_list = []
            for sid, alloc in subject_allocations.items():
                allocated = alloc.get("minutes", 0)
                used = weekly_used.get(sid, 0)
                remaining = allocated - used
                if remaining > 0:
                    data = subject_data.get(sid, {})
                    subject_list.append({
                        "subject_id": sid,
                        "score": data.get("score", 50),
                        "area": data.get("area", "outro"),
                        "performance": data.get("performance", "medium"),
                    })

            if not subject_list:
                continue

            chosen = pick_next_subject(subject_list, recent_subjects, {})
            if not chosen:
                continue

            sid = chosen["subject_id"]
            session_minutes = min(available_minutes, 120)
            session_minutes = max(30, session_minutes)

            end_time = (
                datetime.combine(date.today(), slot_start) +
                timedelta(minutes=session_minutes)
            ).time()

            phase = get_study_phase(
                (exam_date_from_schedule(schedule) - day_date).days
                if schedule else 120
            )
            study_type = recommend_study_type(
                phase,
                chosen.get("performance", "medium"),
                120,
            )

            sessions.append({
                "subject_id": sid,
                "session_date": day_date,
                "start_time": slot_start,
                "end_time": end_time,
                "duration_minutes": session_minutes,
                "study_type": study_type,
            })

            minutes_used_today += session_minutes
            weekly_used[sid] = weekly_used.get(sid, 0) + session_minutes
            recent_subjects.append(sid)

    return sessions


def exam_date_from_schedule(schedule: list[dict]) -> date:
    """Retorna a data mais distante da grade de horários."""
    if not schedule:
        return date.today()
    return max(d["date"] for d in schedule)


def reschedule_missed_sessions(
    missed_sessions: list[dict],
    existing_sessions: list[dict],
    available_days: list[str],
    available_hours: list[str],
    daily_minutes: int,
    exam_date: date,
    today: Optional[date] = None,
) -> list[dict]:
    """
    Reagenda sessões perdidas.

    Sessões perdidas recebem bônus de prioridade e são redistribuídas
    evitando sobrecarregar dias já ocupados.
    """
    today = today or date.today()

    if not missed_sessions:
        return []

    rescheduled = []
    existing_minutes = {}
    for session in existing_sessions:
        d = session.get("session_date")
        if isinstance(d, date):
            existing_minutes[d] = existing_minutes.get(d, 0) + session.get("duration_minutes", 0)

    schedule = generate_session_schedule(
        available_days, available_hours, daily_minutes, exam_date, today
    )

    for missed in missed_sessions:
        subject_id = missed.get("subject_id")
        priority_bonus = missed.get("priority_score", 0) + 20
        placed = False

        for day_info in schedule:
            if placed:
                break
            day_date = day_info["date"]
            used = existing_minutes.get(day_date, 0)

            for slot_start, slot_end in day_info["slots"]:
                slot_minutes = int(
                    (datetime.combine(date.today(), slot_end) -
                     datetime.combine(date.today(), slot_start)).total_seconds() / 60
                )
                remaining = daily_minutes - used
                available = min(slot_minutes, remaining)

                if available >= 30:
                    end_time = (
                        datetime.combine(date.today(), slot_start) +
                        timedelta(minutes=min(available, 60))
                    ).time()

                    rescheduled.append({
                        "subject_id": subject_id,
                        "session_date": day_date,
                        "start_time": slot_start,
                        "end_time": end_time,
                        "duration_minutes": min(available, 60),
                        "study_type": "revisao",
                        "priority_score": priority_bonus,
                        "rescheduled": True,
                    })

                    existing_minutes[day_date] = used + min(available, 60)
                    placed = True
                    break

    return rescheduled
