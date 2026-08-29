from datetime import date
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.tasks import tasks_bp
from app.tasks.forms import TaskForm
from app.models import Task, Subject


@tasks_bp.route("/")
@login_required
def list_tasks():
    filter_status = request.args.get("status", "all")
    filter_subject = request.args.get("subject", type=int)

    query = Task.query.filter_by(user_id=current_user.id)

    if filter_status == "pending":
        query = query.filter_by(concluida=False)
    elif filter_status == "done":
        query = query.filter_by(concluida=True)

    if filter_subject:
        query = query.filter_by(subject_id=filter_subject)

    tasks = query.order_by(Task.data_prevista.asc().nullslast()).all()
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()

    return render_template(
        "tasks/list.html",
        tasks=tasks,
        subjects=subjects,
        filter_status=filter_status,
        filter_subject=filter_subject,
        today=date.today(),
    )


@tasks_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    if not subjects:
        flash("Crie uma materia antes de adicionar tarefas.", "warning")
        return redirect(url_for("subjects.create"))

    form = TaskForm()
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]

    if form.validate_on_submit():
        task = Task(
            titulo=form.titulo.data,
            descricao=form.descricao.data,
            subject_id=form.subject_id.data,
            user_id=current_user.id,
            data_prevista=form.data_prevista.data,
            prioridade=form.prioridade.data,
            concluida=form.concluida.data,
        )
        db.session.add(task)
        db.session.commit()
        flash("Tarefa criada com sucesso!", "success")
        return redirect(url_for("tasks.list_tasks"))

    return render_template("tasks/form.html", form=form, title="Nova Tarefa")


@tasks_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for("tasks.list_tasks"))

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    form = TaskForm(obj=task)
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]

    if form.validate_on_submit():
        task.titulo = form.titulo.data
        task.descricao = form.descricao.data
        task.subject_id = form.subject_id.data
        task.data_prevista = form.data_prevista.data
        task.prioridade = form.prioridade.data
        task.concluida = form.concluida.data
        db.session.commit()
        flash("Tarefa atualizada!", "success")
        return redirect(url_for("tasks.list_tasks"))

    return render_template("tasks/form.html", form=form, title="Editar Tarefa")


@tasks_bp.route("/<int:id>/delete", methods=["GET", "POST"])
@login_required
def delete(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for("tasks.list_tasks"))

    if request.method == "POST":
        db.session.delete(task)
        db.session.commit()
        flash("Tarefa excluida!", "success")
        return redirect(url_for("tasks.list_tasks"))

    return render_template("tasks/confirm_delete.html", task=task)


@tasks_bp.route("/<int:id>/toggle", methods=["POST"])
@login_required
def toggle(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for("tasks.list_tasks"))

    task.concluida = not task.concluida
    db.session.commit()

    status = "concluida" if task.concluida else "reaberta"
    flash(f"Tarefa {status}!", "success")
    return redirect(url_for("tasks.list_tasks"))
