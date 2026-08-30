import calendar
from collections import defaultdict
from datetime import date

from flask import jsonify, render_template
from flask_login import current_user, login_required

from app.main import main_bp
from app.models import StudySession, Subject, Task

WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTHS_PT = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def build_month_grid(year, month, tasks, sessions, today):
    tasks_by_day = defaultdict(list)
    for task in tasks:
        due = task.data_prevista
        if due and due.year == year and due.month == month:
            tasks_by_day[due.day].append(task)

    sessions_by_day = defaultdict(list)
    for session in sessions:
        session_date = session.session_date
        if session_date and session_date.year == year and session_date.month == month:
            sessions_by_day[session_date.day].append(session)

    weeks = []
    for week in calendar.monthcalendar(year, month):
        cells = []
        for day in week:
            if day == 0:
                cells.append(None)
                continue
            cells.append(
                {
                    "day": day,
                    "is_today": today.year == year and today.month == month and today.day == day,
                    "tasks": tasks_by_day.get(day, []),
                    "sessions": sessions_by_day.get(day, []),
                }
            )
        weeks.append(cells)
    return weeks


@main_bp.route("/")
@login_required
def dashboard():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    all_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.data_prevista.asc().nullslast()).all()

    pending_tasks = (
        Task.query.filter_by(user_id=current_user.id, concluida=False)
        .order_by(Task.data_prevista.asc().nullslast())
        .all()
    )

    today = date.today()
    completed_tasks = sum(1 for task in all_tasks if task.concluida)
    overdue_tasks = sum(
        1
        for task in all_tasks
        if (not task.concluida) and task.data_prevista and task.data_prevista < today
    )
    todays_tasks = sum(
        1
        for task in all_tasks
        if (not task.concluida) and task.data_prevista == today
    )

    year, month = today.year, today.month
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)

    sessions = (
        StudySession.query.filter_by(user_id=current_user.id)
        .filter(StudySession.session_date >= month_start, StudySession.session_date < month_end)
        .all()
    )

    board_columns = [
        {
            "title": "Alta",
            "tasks": [task for task in all_tasks if not task.concluida and task.prioridade == "alta"],
        },
        {
            "title": "Média",
            "tasks": [task for task in all_tasks if not task.concluida and task.prioridade == "media"],
        },
        {
            "title": "Baixa",
            "tasks": [task for task in all_tasks if not task.concluida and task.prioridade == "baixa"],
        },
        {
            "title": "Concluídas",
            "tasks": [task for task in all_tasks if task.concluida],
        },
    ]

    return render_template(
        "dashboard.html",
        subjects=subjects,
        pending_tasks=pending_tasks,
        all_tasks=all_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        todays_tasks=todays_tasks,
        today=today,
        calendar_weeks=build_month_grid(year, month, all_tasks, sessions, today),
        weekday_labels=WEEKDAY_LABELS,
        calendar_month_label=f"{MONTHS_PT[month - 1]} {year}",
        board_columns=board_columns,
    )


@main_bp.route("/health")
def health():
    return jsonify({"status": "ok"}), 200
