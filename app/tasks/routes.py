from datetime import date

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.authz import get_user_task
from app.extensions import db
from app.main.stats import mark_task_completion
from app.models import Subject, Task
from app.tasks import tasks_bp
from app.tasks.forms import TaskForm
from app.ai.task_recommender import TaskRecommendationInput
from app.subjects.catalog import provision_subjects

_RECOMMENDATION_ROTATION_KEY = "task_recommendation_subject_ids"


def _safe_next_url():
    candidate = request.form.get("next") or request.args.get("next")
    if candidate and candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return url_for("tasks.list_tasks")


def _select_recommendation_subject(subjects, user_id):
    task_counts = dict(
        db.session.query(Task.subject_id, func.count(Task.id))
        .filter(Task.user_id == user_id)
        .group_by(Task.subject_id)
        .all()
    )
    subject_ids = {subject.id for subject in subjects}
    rotation_ids = [
        subject_id
        for subject_id in session.get(_RECOMMENDATION_ROTATION_KEY, [])
        if isinstance(subject_id, int) and subject_id in subject_ids
    ]
    recent_ids = set(rotation_ids)
    candidates = [subject for subject in subjects if subject.id not in recent_ids]
    if not candidates:
        rotation_ids = []
        candidates = list(subjects)

    selected = min(candidates, key=lambda subject: (task_counts.get(subject.id, 0), subject.id))
    rotation_ids.append(selected.id)
    session[_RECOMMENDATION_ROTATION_KEY] = rotation_ids
    return selected


@tasks_bp.route("/")
@login_required
def list_tasks():
    filter_status = request.args.get("status", "all")
    filter_subject = request.args.get("subject", type=int)
    search_query = (request.args.get("q") or "").strip()

    query = Task.query.filter_by(user_id=current_user.id)

    if filter_status == "pending":
        query = query.filter_by(concluida=False)
    elif filter_status == "done":
        query = query.filter_by(concluida=True)

    if filter_subject:
        query = query.filter_by(subject_id=filter_subject)

    if search_query:
        like = f"%{search_query}%"
        query = query.filter(Task.titulo.ilike(like))

    tasks = query.order_by(Task.data_prevista.asc().nullslast()).all()
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()

    return render_template(
        "tasks/list.html",
        tasks=tasks,
        subjects=subjects,
        filter_status=filter_status,
        filter_subject=filter_subject,
        search_query=search_query,
        today=date.today(),
    )


@tasks_bp.route("/recommend", methods=["POST"])
@login_required
def recommend():
    """Retorna uma tarefa sugerida pela IA sem persistir dados."""
    data = request.get_json(silent=True) or {}
    available_minutes = data.get("available_minutes", 60)
    try:
        available_minutes = int(available_minutes)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "available_minutes invalido"}), 400
    if available_minutes < 15 or available_minutes > 720:
        return jsonify({"success": False, "error": "available_minutes deve estar entre 15 e 720"}), 400

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    if not subjects:
        provision_subjects(current_user.id)
        db.session.commit()
        subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    target_subject = _select_recommendation_subject(subjects, current_user.id)
    pending_tasks = Task.query.filter_by(user_id=current_user.id, concluida=False).all()
    recommendation = current_app.task_recommender.generate(
        TaskRecommendationInput(
            subjects=[subject.nome for subject in subjects],
            weak_subjects=[],
            pending_tasks=[f"{task.titulo} - {task.subject.nome}" for task in pending_tasks],
            available_minutes=available_minutes,
            target_subject=target_subject.nome,
        )
    )
    subject = next((item for item in subjects if item.nome == recommendation.subject), None)
    if subject is None:
        return jsonify({"success": False, "error": "Nenhuma materia disponivel"}), 409

    return jsonify({
        "success": True,
        "recommendation": {
            "title": recommendation.title,
            "description": recommendation.description,
            "subject_id": subject.id,
            "subject": recommendation.subject,
            "study_type": recommendation.study_type,
            "duration_minutes": recommendation.duration_minutes,
            "reason": recommendation.reason,
        },
    }), 200


@tasks_bp.route("/recommend/confirm", methods=["POST"])
@login_required
def confirm_recommendation():
    """Persiste uma recomendacao somente apos confirmacao explicita."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    subject_id = data.get("subject_id")
    duration = data.get("duration_minutes")

    if not title or len(title) > 200 or len(description) > 2000:
        return jsonify({"success": False, "error": "Dados da tarefa invalidos"}), 400
    try:
        subject_id = int(subject_id)
        duration = int(duration)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Materia ou duracao invalidas"}), 400
    if duration < 15 or duration > 720:
        return jsonify({"success": False, "error": "Duracao deve estar entre 15 e 720 minutos"}), 400

    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
    if subject is None:
        return jsonify({"success": False, "error": "Materia nao encontrada"}), 404

    task = Task(
        titulo=title,
        descricao=description,
        subject_id=subject.id,
        user_id=current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"success": True, "task_id": task.id}), 201


@tasks_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    if not subjects:
        flash("Crie uma matéria antes de adicionar tarefas.", "warning")
        return redirect(url_for("subjects.create"))

    form = TaskForm()
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]

    if form.validate_on_submit():
        concluida = form.concluida.data
        if isinstance(concluida, str):
            concluida = concluida.strip().lower() not in {"", "false", "0", "no", "n", "off"}

        task = Task(
            titulo=form.titulo.data,
            descricao=form.descricao.data,
            subject_id=form.subject_id.data,
            user_id=current_user.id,
            data_prevista=form.data_prevista.data,
        )
        mark_task_completion(task, concluida)
        db.session.add(task)
        db.session.commit()
        flash("Tarefa criada com sucesso!", "success")
        return redirect(url_for("tasks.list_tasks"))

    return render_template("tasks/form.html", form=form, title="Nova Tarefa")


@tasks_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    task = get_user_task(id)

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    form = TaskForm(obj=task)
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]

    if form.validate_on_submit():
        concluida = form.concluida.data
        if isinstance(concluida, str):
            concluida = concluida.strip().lower() not in {"", "false", "0", "no", "n", "off"}

        task.titulo = form.titulo.data
        task.descricao = form.descricao.data
        task.subject_id = form.subject_id.data
        task.data_prevista = form.data_prevista.data
        mark_task_completion(task, concluida)
        db.session.commit()
        flash("Tarefa atualizada!", "success")
        return redirect(url_for("tasks.list_tasks"))

    return render_template("tasks/form.html", form=form, title="Editar Tarefa")


@tasks_bp.route("/<int:id>/delete", methods=["GET", "POST"])
@login_required
def delete(id):
    task = get_user_task(id)

    if request.method == "POST":
        db.session.delete(task)
        db.session.commit()
        flash("Tarefa excluída!", "success")
        return redirect(url_for("tasks.list_tasks"))

    return render_template("tasks/confirm_delete.html", task=task)


@tasks_bp.route("/<int:id>/toggle", methods=["POST"])
@login_required
def toggle(id):
    task = get_user_task(id)

    mark_task_completion(task, not task.concluida)
    db.session.commit()

    status = "concluída" if task.concluida else "reaberta"
    flash(f"Tarefa {status}!", "success")
    return redirect(_safe_next_url())
