from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.authz import get_user_subject
from app.areas import infer_area
from app.extensions import db
from app.models import Subject
from app.subjects import subjects_bp
from app.subjects.forms import SubjectForm
from app.subjects.catalog import provision_subjects


@subjects_bp.route("/")
@login_required
def list_subjects():
    provision_subjects(current_user.id)
    db.session.commit()
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    return render_template("subjects/list.html", subjects=subjects)


@subjects_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = SubjectForm()
    if form.validate_on_submit():
        area = form.area.data or "outro"
        if area == "outro":
            area = infer_area(form.nome.data)
        if Subject.query.filter_by(
            user_id=current_user.id,
            nome=form.nome.data,
        ).first():
            flash("Você já possui uma matéria com esse nome.", "warning")
            return render_template("subjects/form.html", form=form, title="Nova Matéria")
        subject = Subject(
            nome=form.nome.data,
            cor=form.cor.data,
            prioridade=form.prioridade.data or 3,
            dificuldade=form.dificuldade.data or 3,
            area=area,
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
    subject = get_user_subject(id)

    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        duplicate = Subject.query.filter(
            Subject.user_id == current_user.id,
            Subject.nome == form.nome.data,
            Subject.id != subject.id,
        ).first()
        if duplicate:
            flash("Você já possui uma matéria com esse nome.", "warning")
            return render_template("subjects/form.html", form=form, title="Editar Matéria")
        subject.nome = form.nome.data
        subject.cor = form.cor.data
        subject.prioridade = form.prioridade.data or 3
        subject.dificuldade = form.dificuldade.data or 3
        subject.area = form.area.data or infer_area(form.nome.data)
        db.session.commit()
        flash("Matéria atualizada!", "success")
        return redirect(url_for("subjects.list_subjects"))

    return render_template("subjects/form.html", form=form, title="Editar Matéria")


@subjects_bp.route("/<int:id>/delete", methods=["GET", "POST"])
@login_required
def delete(id):
    subject = get_user_subject(id)

    if subject.tasks or subject.topics or subject.questions or subject.study_sessions:
        flash(
            "Não é possível excluir matéria com dados vinculados. Remova ou mova os itens primeiro.",
            "warning",
        )
        return redirect(url_for("subjects.list_subjects"))

    if request.method == "POST":
        db.session.delete(subject)
        db.session.commit()
        flash("Matéria excluída!", "success")
        return redirect(url_for("subjects.list_subjects"))

    return render_template("subjects/confirm_delete.html", subject=subject)
