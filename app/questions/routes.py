import logging
import time

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.authz import get_user_question, get_user_subject, get_user_topic
from app.ai.exceptions import (
    AIDisabledError,
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
    AITimeoutError,
    AIRateLimitError,
)
from app.extensions import db
from app.models import Question, Subject, Topic
from app.questions import questions_bp
from app.questions.forms import AnswerForm, QuestionForm, TopicForm
from app.questions.services import (
    create_question,
    create_topic,
    get_attempts_map,
    get_user_attempt,
    get_user_questions,
    get_user_topics,
    record_attempt,
)

logger = logging.getLogger(__name__)


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
    filter_status = (request.args.get("status") or "all").strip().lower()
    if filter_status not in {"all", "pending", "done"}:
        filter_status = "all"
    filter_dificuldade = request.args.get("dificuldade", type=int)
    if filter_dificuldade is not None and filter_dificuldade not in {1, 2, 3, 4, 5}:
        filter_dificuldade = None
    search_query = (request.args.get("q") or "").strip() or None
    page = request.args.get("page", default=1, type=int) or 1
    per_page = request.args.get("per_page", default=20, type=int) or 20
    page = max(1, page)
    per_page = min(50, max(5, per_page))

    questions = get_user_questions(
        current_user.id,
        subject_id=filter_subject,
        topic_id=filter_topic,
        dificuldade=filter_dificuldade,
        search=search_query,
    )
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    topics = get_user_topics(current_user.id, subject_id=filter_subject)
    attempt_map = get_attempts_map(current_user.id, [q.id for q in questions])
    pending_questions = [q for q in questions if q.id not in attempt_map]
    answered_questions = [q for q in questions if q.id in attempt_map]

    if filter_status == "pending":
        visible_questions = pending_questions
    elif filter_status == "done":
        visible_questions = answered_questions
    else:
        visible_questions = questions

    total = len(visible_questions)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_questions = visible_questions[start:end]
    paginated_ids = {q.id for q in paginated_questions}
    paginated_pending = [q for q in pending_questions if q.id in paginated_ids]
    paginated_answered = [q for q in answered_questions if q.id in paginated_ids]
    # Quando há filtro de status, a página contém só aquele grupo;
    # caso contrário, divide a página entre pendentes/concluídas.
    if filter_status == "pending":
        paginated_pending = paginated_questions
        paginated_answered = []
    elif filter_status == "done":
        paginated_pending = []
        paginated_answered = paginated_questions

    return render_template(
        "questions/list.html",
        questions=paginated_questions,
        total_questions=total,
        pending_questions=paginated_pending,
        answered_questions=paginated_answered,
        pending_count=len(pending_questions),
        answered_count=len(answered_questions),
        subjects=subjects,
        topics=topics,
        filter_subject=filter_subject,
        filter_topic=filter_topic,
        filter_status=filter_status,
        filter_dificuldade=filter_dificuldade,
        search_query=search_query or "",
        attempt_map=attempt_map,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@questions_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_question_view():
    abort(404)
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
    attempt = get_user_attempt(current_user.id, id)
    if attempt is None:
        session[f"question_started:{id}"] = time.time()
    return render_template(
        "questions/view.html",
        question=question,
        form=form,
        attempt=attempt,
        explanation=None,
    )


@questions_bp.route("/<int:id>/answer", methods=["POST"])
@login_required
def answer_question(id):
    question = get_user_question(id)
    form = AnswerForm()
    existing_attempt = get_user_attempt(current_user.id, id)

    if existing_attempt is not None:
        flash("Esta questão já foi respondida. Você tem apenas uma tentativa.", "warning")
        return render_template(
            "questions/view.html",
            question=question,
            form=AnswerForm(),
            attempt=existing_attempt,
            explanation=None,
        )

    if form.validate_on_submit():
        started_at = session.pop(f"question_started:{id}", None)
        if started_at:
            elapsed_seconds = int(max(0, time.time() - started_at))
        else:
            # Fallback: sessão expirada ou POST direto (testes/scripts).
            # Usa o tempo enviado no form (hidden) para não perder a info.
            elapsed_seconds = form.tempo_segundos.data
        try:
            attempt = record_attempt(
                user_id=current_user.id,
                question_id=id,
                resposta=form.resposta.data,
                tempo_segundos=elapsed_seconds,
                commit=False,
            )
        except (IntegrityError, ValueError):
            db.session.rollback()
            existing_attempt = get_user_attempt(current_user.id, id)
            if existing_attempt is None:
                raise
            flash("Esta questão já foi respondida. Você tem apenas uma tentativa.", "warning")
            return render_template(
                "questions/view.html",
                question=question,
                form=AnswerForm(),
                attempt=existing_attempt,
                explanation=None,
            )

        explanation = None
        try:
            from app.ai.explanation_generator import ExplanationInput

            mastery = None
            trend = None
            if question.topic_id:
                from app.performance.models import KnowledgeState
                ks = KnowledgeState.query.filter_by(
                    user_id=current_user.id, topic_id=question.topic_id
                ).first()
                if ks:
                    mastery = ks.mastery_score
                    trend = ks.trend

            inp = ExplanationInput(
                question_id=str(question.id),
                statement=question.enunciado,
                alternatives={
                    "a": question.alternativa_a,
                    "b": question.alternativa_b,
                    "c": question.alternativa_c,
                    "d": question.alternativa_d,
                    "e": question.alternativa_e,
                },
                student_answer=attempt.resposta,
                correct_answer=question.resposta_correta,
                materia=question.subject.nome if question.subject else "",
                assunto=question.topic.nome if question.topic else "Geral",
                dificuldade=question.dificuldade,
                mastery=mastery,
                trend=trend,
            )
            explanation = current_app.explanation_generator.generate(inp)
        except Exception as exc:
            logger.warning("Erro ao gerar explicação: %s", exc)

        if attempt.correta:
            flash("Resposta correta!", "success")
        else:
            flash(f"Resposta incorreta. A resposta correta é {question.resposta_correta}.", "danger")

        if question.topic_id:
            from app.performance.services import update_knowledge_state
            update_knowledge_state(
                current_user.id,
                question.topic_id,
                commit=False,
            )

        db.session.commit()

        return render_template(
            "questions/view.html",
            question=question,
            form=AnswerForm(),
            attempt=attempt,
            explanation=explanation,
        )

    logger.warning(
        "Falha ao responder questão id=%s user_id=%s errors=%s",
        id,
        current_user.id,
        form.errors,
    )
    if form.errors.get("csrf_token"):
        flash("Sessão expirada. Recarregue a página e tente novamente.", "warning")
        return redirect(url_for("questions.view_question", id=id))
    if form.resposta.errors:
        flash("Selecione uma alternativa antes de enviar.", "warning")
    elif form.tempo_segundos.errors:
        flash("Tempo de resposta inválido. Tente novamente.", "warning")
    else:
        flash("Formulário inválido. Verifique os campos e tente novamente.", "warning")
    # Re-renderiza (sem redirect) para preservar erros, seleção e timer da sessão.
    return render_template(
        "questions/view.html",
        question=question,
        form=form,
        attempt=None,
        explanation=None,
    )


@questions_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_question(id):
    abort(404)
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


@questions_bp.route("/generate", methods=["POST"])
@login_required
def generate_question():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Corpo da requisição inválido"}), 400

    subject_id = data.get("subject_id")
    topic_id = data.get("topic_id")
    quantidade = data.get("quantidade", 1)

    if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
        return jsonify({"success": False, "error": "subject_id é obrigatório"}), 400

    if isinstance(topic_id, bool) or (topic_id is not None and (
        not isinstance(topic_id, int) or topic_id <= 0
    )):
        return jsonify({"success": False, "error": "topic_id inválido"}), 400

    if isinstance(quantidade, bool) or not isinstance(quantidade, int) or quantidade not in {1, 3, 5}:
        return jsonify({"success": False, "error": "quantidade deve ser 1, 3 ou 5"}), 400

    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
    if not subject:
        return jsonify({"success": False, "error": "Matéria não encontrada"}), 404

    topic = None
    if topic_id:
        topic = Topic.query.filter_by(id=topic_id, user_id=current_user.id).first()
        if not topic or topic.subject_id != subject.id:
            return jsonify({"success": False, "error": "Assunto não encontrado"}), 404

    topic_name = topic.nome if topic else "Geral"
    area = subject.area or "outro"

    try:
        gen = current_app.question_generator
        if not gen.enabled:
            return jsonify({"success": False, "error": "IA não está disponível"}), 503

        generated = gen.generate(
            user_id=str(current_user.id),
            area=area,
            materia=subject.nome,
            assunto=topic_name,
            dificuldade=3,
            quantidade=quantidade,
        )

        if not generated:
            return jsonify({
                "success": False,
                "error": "A IA não conseguiu gerar uma questão válida. Tente novamente.",
            }), 422

        created = []
        for g in generated:
            db_dict = g.to_db_dict()
            new_q = Question(
                enunciado=db_dict["enunciado"],
                alternativa_a=db_dict["alternativa_a"],
                alternativa_b=db_dict["alternativa_b"],
                alternativa_c=db_dict["alternativa_c"],
                alternativa_d=db_dict["alternativa_d"],
                alternativa_e=db_dict["alternativa_e"],
                resposta_correta=db_dict["resposta_correta"],
                subject_id=subject.id,
                topic_id=topic.id if topic else None,
                user_id=current_user.id,
                dificuldade=db_dict["dificuldade"],
                fonte=db_dict.get("fonte", "ai"),
            )
            db.session.add(new_q)
            db.session.flush()
            created.append({
                "id": new_q.id,
                "enunciado": new_q.enunciado,
                "alternativa_a": new_q.alternativa_a,
                "alternativa_b": new_q.alternativa_b,
                "alternativa_c": new_q.alternativa_c,
                "alternativa_d": new_q.alternativa_d,
                "alternativa_e": new_q.alternativa_e,
                "resposta_correta": new_q.resposta_correta,
                "dificuldade": new_q.dificuldade,
            })

        db.session.commit()

        return jsonify({
            "success": True,
            "questions": created,
            "count": len(created),
        }), 201

    except AIDisabledError:
        db.session.rollback()
        return jsonify({"success": False, "error": "IA não está disponível"}), 503
    except AIRateLimitError:
        db.session.rollback()
        return jsonify({"success": False, "error": "Limite do provedor de IA atingido"}), 429
    except ValueError as exc:
        db.session.rollback()
        message = str(exc)
        if "Limite horário" in message:
            return jsonify({"success": False, "error": message}), 429
        return jsonify({"success": False, "error": "Parâmetros inválidos"}), 400
    except AIConfigurationError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": "A IA está habilitada, mas sua configuração está incompleta.",
        }), 503
    except (AIValidationError, AITimeoutError, AIProviderError) as exc:
        db.session.rollback()
        logger.warning("Erro ao gerar questões via IA: %s", exc)
        return jsonify({
            "success": False,
            "error": "Não foi possível gerar questões agora. Tente novamente.",
        }), 502
    except Exception:
        db.session.rollback()
        logger.exception("Erro inesperado ao gerar questões via IA")
        return jsonify({
            "success": False,
            "error": "Erro interno ao gerar questões.",
        }), 500
