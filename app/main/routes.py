from datetime import date

from flask import jsonify, render_template
from flask_login import current_user, login_required

from app.main import main_bp
from app.models import Subject, Task


@main_bp.route("/")
@login_required
def dashboard():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()

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

    priority_summary = {
        "alta": sum(
            1 for task in all_tasks if (not task.concluida) and task.prioridade == "alta"
        ),
        "media": sum(
            1 for task in all_tasks if (not task.concluida) and task.prioridade == "media"
        ),
        "baixa": sum(
            1 for task in all_tasks if (not task.concluida) and task.prioridade == "baixa"
        ),
    }

    upcoming_tasks = (
        Task.query.filter_by(user_id=current_user.id, concluida=False)
        .filter(Task.data_prevista.isnot(None))
        .filter(Task.data_prevista >= today)
        .order_by(Task.data_prevista.asc(), Task.prioridade.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        subjects=subjects,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        todays_tasks=todays_tasks,
        priority_summary=priority_summary,
        upcoming_tasks=upcoming_tasks,
        today=today,
    )


@main_bp.route("/health")
def health():
    return jsonify({"status": "ok"}), 200
