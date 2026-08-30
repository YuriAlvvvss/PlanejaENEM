from datetime import date, datetime, timedelta, timezone

from app.areas import AREA_LABELS, area_label, infer_area
from app.models import StudyPlan, StudySession, Subject, Task

REVIEW_INTERVAL_DAYS = 7
WEEK_COUNT = 8
DEFAULT_WEEKLY_GOAL_MINUTES = 600


def start_of_week(day):
    return day - timedelta(days=day.weekday())


def format_hours(minutes):
    minutes = max(0, int(minutes or 0))
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h {remainder}min"
    if hours:
        return f"{hours}h"
    return f"{remainder}min"


def resolved_area(subject):
    if subject.area and subject.area != "outro":
        return subject.area
    return infer_area(subject.nome)


def weekly_goal_minutes(user, plan=None):
    stored = getattr(user, "weekly_goal_minutes", None)
    if stored:
        return int(stored)
    plan = plan or (
        StudyPlan.query.filter_by(user_id=user.id).order_by(StudyPlan.generated_at.desc()).first()
    )
    if plan and plan.daily_minutes and plan.days_list:
        return int(plan.daily_minutes) * max(1, len(plan.days_list))
    return DEFAULT_WEEKLY_GOAL_MINUTES


def activity_dates_for_user(user_id, tasks, sessions):
    dates = set()
    for session in sessions:
        if session.completed and session.session_date:
            dates.add(session.session_date)
    for task in tasks:
        if task.concluida and task.completed_at:
            completed_day = task.completed_at.date()
            dates.add(completed_day)
        elif task.concluida and task.data_prevista:
            dates.add(task.data_prevista)
    return dates


def compute_streak(activity_dates, today):
    if not activity_dates:
        return 0
    cursor = today if today in activity_dates else today - timedelta(days=1)
    if cursor not in activity_dates:
        return 0
    streak = 0
    while cursor in activity_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _minutes_in_range(sessions, start, end, completed_only=False):
    total = 0
    for session in sessions:
        session_date = session.session_date
        if not session_date or session_date < start or session_date >= end:
            continue
        if completed_only and not session.completed:
            continue
        total += int(session.duration_minutes or 0)
    return total


def build_dashboard_stats(user, today=None):
    today = today or date.today()
    week_start = start_of_week(today)
    week_end = week_start + timedelta(days=7)
    review_horizon = today + timedelta(days=14)

    subjects = Subject.query.filter_by(user_id=user.id).order_by(Subject.nome).all()
    tasks = Task.query.filter_by(user_id=user.id).all()
    sessions = StudySession.query.filter_by(user_id=user.id).all()
    plan = StudyPlan.query.filter_by(user_id=user.id).order_by(StudyPlan.generated_at.desc()).first()

    planned_week = _minutes_in_range(sessions, week_start, week_end, completed_only=False)
    completed_week = _minutes_in_range(sessions, week_start, week_end, completed_only=True)
    goal_minutes = weekly_goal_minutes(user, plan)
    weekly_progress = min(100, round((completed_week / goal_minutes) * 100)) if goal_minutes else 0

    todays_tasks = [
        task
        for task in tasks
        if (not task.concluida) and task.data_prevista == today
    ]
    overdue_tasks = sorted(
        [
            task
            for task in tasks
            if (not task.concluida) and task.data_prevista and task.data_prevista < today
        ],
        key=lambda task: task.data_prevista,
    )
    upcoming_tasks = sorted(
        [
            task
            for task in tasks
            if (not task.concluida)
            and task.data_prevista
            and today < task.data_prevista <= today + timedelta(days=14)
        ],
        key=lambda task: task.data_prevista,
    )
    upcoming_reviews = sorted(
        [
            task
            for task in tasks
            if task.concluida
            and task.next_review_date
            and task.next_review_date <= review_horizon
        ],
        key=lambda task: (task.next_review_date, task.titulo),
    )
    overdue_reviews = [task for task in upcoming_reviews if task.next_review_date < today]
    due_reviews = [task for task in upcoming_reviews if task.next_review_date >= today]

    todays_sessions = sorted(
        [session for session in sessions if session.session_date == today],
        key=lambda session: session.start_time or datetime.min.time(),
    )

    area_stats = []
    for area_key, label in AREA_LABELS.items():
        area_subjects = [subject for subject in subjects if resolved_area(subject) == area_key]
        if not area_subjects and area_key == "outro":
            continue
        area_tasks = [task for task in tasks if task.subject in area_subjects]
        total = len(area_tasks)
        done = sum(1 for task in area_tasks if task.concluida)
        minutes = sum(
            int(session.duration_minutes or 0)
            for session in sessions
            if session.completed and session.subject in area_subjects
        )
        if not area_subjects and total == 0:
            continue
        area_stats.append(
            {
                "key": area_key,
                "label": label,
                "subjects": len(area_subjects),
                "total_tasks": total,
                "completed_tasks": done,
                "percent": round((done / total) * 100) if total else 0,
                "minutes": minutes,
            }
        )

    subject_time = []
    for subject in subjects:
        planned = sum(
            int(session.duration_minutes or 0)
            for session in sessions
            if session.subject_id == subject.id
        )
        completed = sum(
            int(session.duration_minutes or 0)
            for session in sessions
            if session.subject_id == subject.id and session.completed
        )
        subject_time.append(
            {
                "id": subject.id,
                "nome": subject.nome,
                "cor": subject.cor,
                "area": area_label(resolved_area(subject)),
                "planned_minutes": planned,
                "completed_minutes": completed,
                "progress_percent": subject.progress_percent,
            }
        )

    week_labels = []
    planned_series = []
    completed_series = []
    completion_series = []
    for offset in range(WEEK_COUNT - 1, -1, -1):
        period_start = week_start - timedelta(days=7 * offset)
        period_end = period_start + timedelta(days=7)
        week_labels.append(period_start.strftime("%d/%m"))
        planned_series.append(round(_minutes_in_range(sessions, period_start, period_end) / 60, 1))
        completed_series.append(
            round(_minutes_in_range(sessions, period_start, period_end, completed_only=True) / 60, 1)
        )
        due_in_week = [
            task
            for task in tasks
            if task.data_prevista and period_start <= task.data_prevista < period_end
        ]
        if due_in_week:
            done_in_week = sum(1 for task in due_in_week if task.concluida)
            completion_series.append(round((done_in_week / len(due_in_week)) * 100))
        else:
            completion_series.append(0)

    streak = compute_streak(activity_dates_for_user(user.id, tasks, sessions), today)
    completed_tasks = sum(1 for task in tasks if task.concluida)

    charts = {
        "hoursPerWeek": {
            "labels": week_labels,
            "planned": planned_series,
            "completed": completed_series,
        },
        "timeBySubject": {
            "labels": [item["nome"] for item in subject_time],
            "minutes": [round(item["completed_minutes"] / 60, 1) for item in subject_time],
            "colors": [item["cor"] for item in subject_time],
        },
        "progressByArea": {
            "labels": [item["label"] for item in area_stats],
            "percent": [item["percent"] for item in area_stats],
        },
        "evolution": {
            "labels": week_labels,
            "values": completion_series,
        },
    }

    return {
        "today": today,
        "subjects": subjects,
        "plan": plan,
        "planned_minutes": planned_week,
        "completed_minutes": completed_week,
        "planned_hours_label": format_hours(planned_week),
        "completed_hours_label": format_hours(completed_week),
        "goal_minutes": goal_minutes,
        "goal_hours_label": format_hours(goal_minutes),
        "goal_hours_input": round(goal_minutes / 60, 1),
        "weekly_progress": weekly_progress,
        "streak": streak,
        "completed_tasks": completed_tasks,
        "all_tasks_count": len(tasks),
        "todays_tasks": todays_tasks,
        "overdue_tasks": overdue_tasks,
        "upcoming_tasks": upcoming_tasks,
        "upcoming_reviews": due_reviews,
        "overdue_reviews": overdue_reviews,
        "todays_sessions": todays_sessions,
        "area_stats": area_stats,
        "subject_time": subject_time,
        "charts": charts,
    }


def mark_task_completion(task, completed):
    task.concluida = completed
    if completed:
        now = datetime.now(timezone.utc)
        task.completed_at = now
        task.next_review_date = now.date() + timedelta(days=REVIEW_INTERVAL_DAYS)
    else:
        task.completed_at = None
        task.next_review_date = None
