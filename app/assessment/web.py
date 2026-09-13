"""
Rotas HTML da avaliação adaptativa - P2.1.

Camada fina sobre services.py (mesma fonte do REST).
Nenhuma decisão de dificuldade/mastery aqui — só orquestra
formulários, PRG, CSRF e empty-states.

Rotas (sem colidir com o REST JSON em routes.py):
  GET  /assessment/              - hub (iniciar + continuar + últimas)
  POST /assessment/new           - iniciar via form (target 5-30 + matéria?)
  GET  /assessment/<id>          - jogador (1 questão por vez)
  POST /assessment/<id>/respond  - responder via form (PRG)
  GET  /assessment/<id>/result   - resultado (idempotente)
  POST /assessment/<id>/abandon  - desistir (active -> abandoned)
"""

import logging
import time

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.assessment import assessment_bp
from app.assessment.models import Assessment, AssessmentQuestion
from app.assessment.services import (
    complete_assessment,
    get_assessment_status,
    get_next_question,
    list_user_assessments,
    start_assessment,
    submit_answer,
)
from app.extensions import db
from app.models import Question, Subject
from app.performance.models import KnowledgeState

logger = logging.getLogger(__name__)


def _get_owned_assessment(assessment_id: int) -> Assessment:
    assessment = Assessment.query.filter_by(
        id=assessment_id, user_id=current_user.id
    ).first()
    if assessment is None:
        from flask import abort

        abort(404)
    return assessment


def _get_pending_aq(assessment_id: int):
    return (
        AssessmentQuestion.query.filter_by(
            assessment_id=assessment_id,
            user_id=current_user.id,
            resposta=None,
        )
        .order_by(AssessmentQuestion.order.desc())
        .first()
    )


@assessment_bp.route("/", methods=["GET"])
@login_required
def index():
    from flask import request as flask_request

    raw_status = (flask_request.args.get("status") or "all").strip().lower()
    if raw_status not in {"all", "active", "completed", "abandoned"}:
        raw_status = "all"
    status_filter = None if raw_status == "all" else raw_status
    try:
        page = int(flask_request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(flask_request.args.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    page = max(1, page)
    per_page = max(5, min(20, per_page))

    # Card "Em andamento" sempre visível, independente do filtro.
    active_list = list_user_assessments(
        user_id=current_user.id, status="active", limit=1
    )
    active = active_list[0] if active_list else None

    # Total para paginação (limit 100 = teto seguro; avaliações são poucas).
    all_filtered = list_user_assessments(
        user_id=current_user.id, status=status_filter, limit=100
    )
    total = len(all_filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    assessments = all_filtered[start:start + per_page]

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(
        Subject.nome
    ).all()
    ks_count = KnowledgeState.query.filter_by(user_id=current_user.id).count()

    # Digest on-site (2 contagens leves, mesmos critérios do dashboard).
    # Só calcula para quem optou — perfil controla via /auth/notification-preference.
    digest = None
    if getattr(current_user, "email_opt_in", False):
        from datetime import date as date_cls

        from app.models import Task

        today = date_cls.today()
        overdue_count = (
            Task.query.filter_by(user_id=current_user.id, concluida=False)
            .filter(
                Task.data_prevista.is_not(None),
                Task.data_prevista < today,
            )
            .count()
        )
        reviews_due = (
            Task.query.filter_by(user_id=current_user.id, concluida=True)
            .filter(
                Task.next_review_date.is_not(None),
                Task.next_review_date <= today,
            )
            .count()
        )
        digest = {"overdue": overdue_count, "reviews": reviews_due}

    return render_template(
        "assessment/index.html",
        assessments=assessments,
        total=total,
        active=active,
        subjects=subjects,
        ks_count=ks_count,
        digest=digest,
        filter_status=raw_status,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@assessment_bp.route("/new", methods=["POST"])
@login_required
def start_web():
    try:
        target = int(request.form.get("target_questions", 10))
    except (TypeError, ValueError):
        target = 10
    target = max(5, min(30, target))
    subject_id = request.form.get("subject_id", type=int) or None
    try:
        assessment = start_assessment(
            user_id=current_user.id,
            target_questions=target,
            subject_id=subject_id,
        )
    except ValueError as exc:
        flash(str(exc), "warning")
        # Sem KnowledgeState -> CTA para responder questões primeiro.
        return redirect(url_for("assessment.index"))
    return redirect(url_for("assessment.play", assessment_id=assessment.id))


@assessment_bp.route("/<int:assessment_id>", methods=["GET"])
@login_required
def play(assessment_id: int):
    assessment = _get_owned_assessment(assessment_id)
    if assessment.status != "active":
        return redirect(
            url_for("assessment.result", assessment_id=assessment.id)
        )

    pending = _get_pending_aq(assessment.id)
    if pending is None:
        try:
            nxt = get_next_question(assessment.id, current_user.id)
        except ValueError as exc:
            # Completa ou sem tópico: finaliza de forma idempotente.
            logger.info("Avaliação %s sem próxima: %s", assessment.id, exc)
            return redirect(
                url_for("assessment.result", assessment_id=assessment.id)
            )
        pending = AssessmentQuestion.query.filter_by(
            id=nxt.get("assessment_question_id"), user_id=current_user.id
        ).first()
        if pending is None:
            flash("Não foi possível carregar a próxima questão.", "warning")
            return redirect(url_for("assessment.index"))

    question = None
    if pending.question_id:
        question = Question.query.filter_by(
            id=pending.question_id, user_id=current_user.id
        ).first()
    if question is None and pending.generated_question_data:
        # IA desligada ou banco esgotado: mostra params + CTA, sem 500.
        return render_template(
            "assessment/pending_generation.html",
            assessment=assessment.to_dict(),
            pending=pending,
        )
    if question is None:
        flash("Questão não encontrada. Tente outra matéria.", "warning")
        return redirect(url_for("assessment.index"))

    session[f"assessment_started:{pending.id}"] = time.time()
    status = get_assessment_status(assessment.id, current_user.id)
    return render_template(
        "assessment/play.html",
        assessment=status,
        pending=pending,
        question=question,
    )


@assessment_bp.route("/<int:assessment_id>/respond", methods=["POST"])
@login_required
def respond(assessment_id: int):
    assessment = _get_owned_assessment(assessment_id)
    if assessment.status != "active":
        return redirect(
            url_for("assessment.result", assessment_id=assessment.id)
        )
    aq_id = request.form.get("assessment_question_id", type=int)
    resposta = (request.form.get("resposta") or "").strip().upper()
    if not aq_id:
        flash("Questão inválida. Recarregue e tente novamente.", "warning")
        return redirect(url_for("assessment.play", assessment_id=assessment.id))
    if resposta not in {"A", "B", "C", "D", "E"}:
        flash("Selecione uma alternativa antes de enviar.", "warning")
        return redirect(url_for("assessment.play", assessment_id=assessment.id))

    started_at = session.pop(f"assessment_started:{aq_id}", None)
    if started_at:
        tempo = int(max(0, time.time() - started_at))
    else:
        try:
            tempo = int(request.form.get("tempo_segundos", 0))
        except (TypeError, ValueError):
            tempo = None
    try:
        result = submit_answer(
            assessment_id=assessment.id,
            assessment_question_id=aq_id,
            user_id=current_user.id,
            resposta=resposta,
            tempo_segundos=tempo,
        )
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("assessment.play", assessment_id=assessment.id))

    if result.get("is_complete"):
        flash(
            f"Avaliação concluída: {result['assessment_progress']['correct_count']}"
            f"/{result['assessment_progress']['target']} acertos.",
            "success" if result.get("correta") else "info",
        )
        return redirect(
            url_for("assessment.result", assessment_id=assessment.id)
        )
    flash(
        "Resposta correta!" if result.get("correta") else "Resposta incorreta.",
        "success" if result.get("correta") else "danger",
    )
    # PRG: volta ao jogador, que carrega a próxima (já criada pelo service).
    return redirect(url_for("assessment.play", assessment_id=assessment.id))


@assessment_bp.route("/<int:assessment_id>/result", methods=["GET"])
@login_required
def result(assessment_id: int):
    _get_owned_assessment(assessment_id)
    try:
        result_data = complete_assessment(assessment_id, current_user.id)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("assessment.index"))
    status = get_assessment_status(assessment_id, current_user.id)
    return render_template(
        "assessment/result.html",
        assessment=status,
        result=result_data,
    )


@assessment_bp.route("/<int:assessment_id>/abandon", methods=["POST"])
@login_required
def abandon(assessment_id: int):
    assessment = _get_owned_assessment(assessment_id)
    if assessment.is_active:
        assessment.status = "abandoned"
        from datetime import datetime, timezone

        assessment.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Avaliação abandonada.", "info")
    return redirect(url_for("assessment.index"))
