"""
Rotas do planner adaptativo - PlanejaENEM Adaptive Planner v2.

Responsável por:
- HTTP e autenticação
- Receber formulários
- Chamar serviços
- Retornar respostas
"""

from datetime import date, datetime

from flask import current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.authz import get_user_plan, get_user_session, user_owns_subject
from app.extensions import db, limiter
from app.models import StudyPlan, StudySession, Subject
from app.planner import planner_bp
from app.planner.services import (
    generate_adaptive_plan,
    process_planner_request,
    replan_after_missed_sessions,
    get_diagnostics,
    get_subject_need_data,
)


@planner_bp.route("/", methods=["GET", "POST"])
@login_required
@limiter.limit("10/minute")
def planner():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    existing_plan = StudyPlan.query.filter_by(user_id=current_user.id).order_by(
        StudyPlan.generated_at.desc()
    ).first()

    if request.method == "POST":
        result, errors = process_planner_request(
            user_id=current_user.id,
            form_data=request.form,
            subjects=subjects,
        )

        if errors:
            for error in errors:
                flash(error, "warning")
            return render_template(
                "planner/planner.html",
                subjects=subjects,
                active_plan=existing_plan,
                mode="form",
            )

        if not result.get("sessions"):
            flash(
                "Não foi possível gerar um cronograma com a disponibilidade informada. Ajuste dias e horários.",
                "warning",
            )
            return render_template(
                "planner/planner.html",
                subjects=subjects,
                active_plan=existing_plan,
                mode="form",
            )

        exam_date_str = request.form.get("exam_date", "")
        exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d").date()

        daily_minutes = request.form.get("daily_minutes", 60, type=int)
        available_days = request.form.getlist("available_days")
        available_hours = request.form.get("available_hours", "")

        from app.planner.validators import validate_available_days
        days_valid, _ = validate_available_days(available_days)

        plan = StudyPlan(
            user_id=current_user.id,
            exam_date=exam_date,
            daily_minutes=daily_minutes,
            available_days=",".join(days_valid),
            available_hours=available_hours,
            is_active=True,
            generated_at=datetime.now().replace(tzinfo=None),
        )
        db.session.add(plan)
        db.session.flush()

        StudyPlan.query.filter(
            StudyPlan.user_id == current_user.id,
            StudyPlan.id != plan.id,
        ).update({"is_active": False})

        for session_data in result["sessions"]:
            start_time = session_data.get("start_time")
            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, "%H:%M").time()

            end_time = session_data.get("end_time")
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, "%H:%M").time()

            db.session.add(
                StudySession(
                    plan_id=plan.id,
                    user_id=current_user.id,
                    subject_id=session_data["subject_id"],
                    session_date=session_data["session_date"],
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=session_data.get("duration_minutes", 60),
                    priority_score=session_data.get("priority_score", 0),
                    session_type=session_data.get("study_type", "teoria"),
                    manual_override=False,
                )
            )

        db.session.commit()

        summary = result.get("summary", {})
        sessions_count = summary.get("total_sessions", 0)
        total_hours = summary.get("total_hours", 0)
        phase = summary.get("phase", "")
        phase_labels = {
            "long_term": "Longo Prazo",
            "medium_term": "Médio Prazo",
            "final_stretch": "Reta Final",
        }
        phase_label = phase_labels.get(phase, phase)

        flash(
            f"Cronograma gerado com sucesso! {sessions_count} sessões ({total_hours}h) - Fase: {phase_label}",
            "success",
        )
        return redirect(url_for("planner.planner"))

    return render_template(
        "planner/planner.html",
        subjects=subjects,
        active_plan=existing_plan,
        mode="form",
    )


@planner_bp.route("/<int:id>/regenerate", methods=["POST"])
@login_required
def regenerate(id):
    plan = get_user_plan(id)
    
    plan.is_active = False
    plan.last_regenerated_at = datetime.now().replace(tzinfo=None)
    
    db.session.commit()
    flash("Plano anterior arquivado. Gere um novo planejamento.", "info")
    return redirect(url_for("planner.planner"))


@planner_bp.route("/<int:id>/manual", methods=["POST"])
@login_required
def update_manual(id):
    study_session = get_user_session(id)
    study_session.manual_override = True
    study_session.notes = request.form.get("notes", study_session.notes)
    if request.form.get("subject_id"):
        new_subject_id = int(request.form.get("subject_id"))
        if not user_owns_subject(new_subject_id):
            flash("Matéria inválida.", "danger")
            return redirect(url_for("planner.planner"))
        study_session.subject_id = new_subject_id
    db.session.commit()
    flash("Sessão atualizada manualmente.", "success")
    return redirect(url_for("planner.planner"))


@planner_bp.route("/replan", methods=["POST"])
@login_required
def replan():
    """Replaneja sessões perdidas."""
    result = replan_after_missed_sessions(current_user.id)

    missed_count = result.get("missed_count", 0)
    rescheduled_count = result.get("rescheduled_count", 0)

    if missed_count > 0:
        flash(
            f"{missed_count} sessão(ões) perdida(s) detectada(s). "
            f"{rescheduled_count} sessão(ões) reagendada(s).",
            "info",
        )
    else:
        flash("Nenhuma sessão perdida detectada.", "success")

    return redirect(url_for("planner.planner"))


@planner_bp.route("/diagnostics", methods=["GET"])
@login_required
def diagnostics():
    """Exibe diagnóstico do desempenho do aluno."""
    diagnostics_data = get_diagnostics(current_user.id)
    return render_template("planner/diagnostics.html", diagnostics=diagnostics_data)


@planner_bp.route("/review", methods=["POST"])
@login_required
def generate_review():
    """Gera revisão personalizada para um tópico via IA."""
    import logging
    logger = logging.getLogger(__name__)

    data = request.get_json(silent=True) or {}
    topic_id = data.get("topic_id")
    duration_minutes = data.get("duration_minutes", 10)

    if not topic_id:
        return jsonify({"success": False, "error": "topic_id é obrigatório"}), 400

    from app.performance.models import KnowledgeState
    from app.models import Topic

    topic = Topic.query.filter_by(id=topic_id, user_id=current_user.id).first()
    if not topic:
        return jsonify({"success": False, "error": "Tópico não encontrado"}), 404

    ks = KnowledgeState.query.filter_by(
        user_id=current_user.id, topic_id=topic_id
    ).first()

    mastery = ks.mastery_score if ks else 0.0
    confidence = ks.confidence_score if ks else 0.0

    weak_concepts = []
    recent_errors = []
    if ks:
        if ks.mastery_score < 0.5:
            weak_concepts.append(topic.nome)
        if ks.trend == "declining":
            recent_errors.append(f"Tendência em declínio em {topic.nome}")

    try:
        from app.ai.review_generator import ReviewInput

        inp = ReviewInput(
            materia=topic.subject.nome if topic.subject else "",
            assunto=topic.nome,
            mastery=mastery,
            confidence=confidence,
            weak_concepts=weak_concepts,
            recent_errors=recent_errors,
            duration_minutes=int(duration_minutes),
        )
        review = current_app.review_generator.generate(inp)

        return jsonify({
            "success": True,
            "review": {
                "title": review.title,
                "summary": review.summary,
                "key_concepts": review.key_concepts,
                "worked_example": review.worked_example,
                "common_mistakes": review.common_mistakes,
                "quick_check": review.quick_check,
            },
        }), 200

    except Exception as exc:
        logger.warning("Erro ao gerar revisão: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500
