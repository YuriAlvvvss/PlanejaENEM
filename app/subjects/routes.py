from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.subjects import subjects_bp
from app.subjects.forms import SubjectForm
from app.models import Subject


@subjects_bp.route("/")
@login_required
def list_subjects():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    return render_template("subjects/list.html", subjects=subjects)


@subjects_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(
            nome=form.nome.data,
            cor=form.cor.data,
            user_id=current_user.id,
        )
        db.session.add(subject)
        db.session.commit()
        flash("Matéria criada com sucesso!", "success")
        return redirect(url_for("subjects.list_subjects"))

    return render_template("subjects/form.html", form=form, title="Nova Matéria")


@subjects_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    subject = Subject.query.filter_by(user_id=current_user.id).filter_by(id=id).first_or_404()

    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        subject.nome = form.nome.data
        subject.cor = form.cor.data
        db.session.commit()
        flash("Matéria atualizada!", "success")
        return redirect(url_for("subjects.list_subjects"))

    return render_template("subjects/form.html", form=form, title="Editar Matéria")


@subjects_bp.route("/<int:id>/delete", methods=["GET", "POST"])
@login_required
def delete(id):
    subject = Subject.query.filter_by(user_id=current_user.id).filter_by(id=id).first_or_404()

    if subject.tasks:
        flash(
            "Não é possível excluir matéria com tarefas vinculadas. Remova as tarefas primeiro.",
            "warning",
        )
        return redirect(url_for("subjects.list_subjects"))

    if __import__("flask").request.method == "POST":
        db.session.delete(subject)
        db.session.commit()
        flash("Matéria excluída!", "success")
        return redirect(url_for("subjects.list_subjects"))

    return render_template("subjects/confirm_delete.html", subject=subject)
