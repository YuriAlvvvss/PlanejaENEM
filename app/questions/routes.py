from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.authz import get_user_question, get_user_subject, get_user_topic
from app.extensions import db
from app.models import Question, Subject, Topic
from app.questions import questions_bp
from app.questions.forms import AnswerForm, QuestionForm, TopicForm
from app.questions.services import (
    create_question,
    create_topic,
    get_recent_attempts,
    get_user_attempt_count,
    get_user_questions,
    get_user_topics,
    record_attempt,
)


@questions_bp.route("/topics")
@login_required
def list_topics():
    topics = get_user_topics(current_user.id)
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    return render_template("questions/topics.html", topics=topics, subjects=subjects)


@questions_bp.route("/topics/new", methods=["GET", "POST"])
@login_required
def create_topic_view():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    if not subjects:
        flash("Crie uma matéria antes de criar assuntos.", "warning")
        return redirect(url_for("subjects.create"))

    form = TopicForm()
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]

    if form.validate_on_submit():
        create_topic(
            nome=form.nome.data,
            subject_id=form.subject_id.data,
            user_id=current_user.id,
        )
        flash("Assunto criado com sucesso!", "success")
        return redirect(url_for("questions.list_topics"))

    return render_template("questions/topic_form.html", form=form, title="Novo Assunto")


@questions_bp.route("/topics/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_topic(id):
    topic = get_user_topic(id)
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    form = TopicForm(obj=topic)
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]

    if form.validate_on_submit():
        topic.nome = form.nome.data
        topic.subject_id = form.subject_id.data
        db.session.commit()
        flash("Assunto atualizado!", "success")
        return redirect(url_for("questions.list_topics"))

    return render_template("questions/topic_form.html", form=form, title="Editar Assunto")


@questions_bp.route("/topics/<int:id>/delete", methods=["GET", "POST"])
@login_required
def delete_topic(id):
    topic = get_user_topic(id)
    if request.method == "POST":
        db.session.delete(topic)
        db.session.commit()
        flash("Assunto excluído!", "success")
        return redirect(url_for("questions.list_topics"))
    return render_template("questions/confirm_delete_topic.html", topic=topic)


@questions_bp.route("/")
@login_required
def list_questions():
    filter_subject = request.args.get("subject", type=int)
    filter_topic = request.args.get("topic", type=int)
    questions = get_user_questions(current_user.id, subject_id=filter_subject, topic_id=filter_topic)
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    topics = get_user_topics(current_user.id, subject_id=filter_subject)
    return render_template(
        "questions/list.html",
        questions=questions,
        subjects=subjects,
        topics=topics,
        filter_subject=filter_subject,
        filter_topic=filter_topic,
    )


@questions_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_question_view():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    if not subjects:
        flash("Crie uma matéria antes de criar questões.", "warning")
        return redirect(url_for("subjects.create"))

    form = QuestionForm()
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]
    topics = get_user_topics(current_user.id)
    form.topic_id.choices = [(0, "-- Nenhum --")] + [(t.id, f"{t.subject.nome} - {t.nome}") for t in topics]

    if request.method == "GET":
        subject_id = request.args.get("subject", type=int)
        if subject_id:
            form.subject_id.data = subject_id

    if form.validate_on_submit():
        topic_id = form.topic_id.data if form.topic_id.data else None
        create_question(
            enunciado=form.enunciado.data,
            alternativa_a=form.alternativa_a.data,
            alternativa_b=form.alternativa_b.data,
            alternativa_c=form.alternativa_c.data,
            alternativa_d=form.alternativa_d.data,
            alternativa_e=form.alternativa_e.data,
            resposta_correta=form.resposta_correta.data,
            subject_id=form.subject_id.data,
            user_id=current_user.id,
            topic_id=topic_id,
            dificuldade=form.dificuldade.data or 3,
            ano=form.ano.data,
            fonte=form.fonte.data,
        )
        flash("Questão criada com sucesso!", "success")
        return redirect(url_for("questions.list_questions"))

    return render_template("questions/question_form.html", form=form, title="Nova Questão")


@questions_bp.route("/<int:id>")
@login_required
def view_question(id):
    question = get_user_question(id)
    form = AnswerForm()
    attempt_count = get_user_attempt_count(current_user.id, id)
    recent_attempts = get_recent_attempts(current_user.id, limit=5)
    return render_template(
        "questions/view.html",
        question=question,
        form=form,
        attempt_count=attempt_count,
        recent_attempts=recent_attempts,
    )


@questions_bp.route("/<int:id>/answer", methods=["POST"])
@login_required
def answer_question(id):
    question = get_user_question(id)
    form = AnswerForm()

    if form.validate_on_submit():
        attempt = record_attempt(
            user_id=current_user.id,
            question_id=id,
            resposta=form.resposta.data,
            tempo_segundos=form.tempo_segundos.data,
        )
        if attempt.correta:
            flash("Resposta correta!", "success")
        else:
            flash(f"Resposta incorreta. A resposta correta é {question.resposta_correta}.", "danger")
        return redirect(url_for("questions.view_question", id=id))

    flash("Formulário inválido.", "warning")
    return redirect(url_for("questions.view_question", id=id))


@questions_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_question(id):
    question = get_user_question(id)
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    form = QuestionForm(obj=question)
    form.subject_id.choices = [(s.id, s.nome) for s in subjects]
    topics = get_user_topics(current_user.id)
    form.topic_id.choices = [(0, "-- Nenhum --")] + [(t.id, f"{t.subject.nome} - {t.nome}") for t in topics]

    if form.validate_on_submit():
        question.enunciado = form.enunciado.data
        question.alternativa_a = form.alternativa_a.data
        question.alternativa_b = form.alternativa_b.data
        question.alternativa_c = form.alternativa_c.data
        question.alternativa_d = form.alternativa_d.data
        question.alternativa_e = form.alternativa_e.data
        question.resposta_correta = form.resposta_correta.data
        question.subject_id = form.subject_id.data
        question.topic_id = form.topic_id.data if form.topic_id.data else None
        question.dificuldade = form.dificuldade.data or 3
        question.ano = form.ano.data
        question.fonte = form.fonte.data
        db.session.commit()
        flash("Questão atualizada!", "success")
        return redirect(url_for("questions.view_question", id=id))

    return render_template("questions/question_form.html", form=form, title="Editar Questão")


@questions_bp.route("/<int:id>/delete", methods=["GET", "POST"])
@login_required
def delete_question(id):
    question = get_user_question(id)
    if request.method == "POST":
        db.session.delete(question)
        db.session.commit()
        flash("Questão excluída!", "success")
        return redirect(url_for("questions.list_questions"))
    return render_template("questions/confirm_delete_question.html", question=question)
