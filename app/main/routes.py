from datetime import UTC, datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.authz import get_user_session
from app.extensions import db
from app.main import main_bp
from app.main.stats import build_dashboard_stats
from app.models import Question, Subject, Task, Topic


def _safe_next_url(default_endpoint="main.dashboard"):
    candidate = request.form.get("next") or request.args.get("next")
    if candidate and candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return url_for(default_endpoint)


@main_bp.route("/")
@login_required
def dashboard():
    stats = build_dashboard_stats(current_user)
    return render_template("dashboard.html", **stats)


@main_bp.route("/search")
@login_required
def search():
    search_query = (request.args.get("q") or "").strip()
    result_type = (request.args.get("type") or "all").strip().lower()
    if result_type not in {"all", "subject", "topic", "task", "question"}:
        result_type = "all"
    results = {
        "subjects": [],
        "topics": [],
        "tasks": [],
        "questions": [],
    }

    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    if search_query:
        like = f"%{_escape_like(search_query)}%"
        escape_clause = {"escape": "\\"}
        if result_type in {"all", "subject"}:
            results["subjects"] = Subject.query.filter(
                Subject.user_id == current_user.id,
                Subject.nome.ilike(like, **escape_clause),
            ).order_by(Subject.nome).limit(25).all()
        if result_type in {"all", "topic"}:
            results["topics"] = Topic.query.filter(
                Topic.user_id == current_user.id,
                Topic.nome.ilike(like, **escape_clause),
            ).order_by(Topic.nome).limit(25).all()
        if result_type in {"all", "task"}:
            results["tasks"] = Task.query.filter(
                Task.user_id == current_user.id,
                or_(Task.titulo.ilike(like, **escape_clause), Task.descricao.ilike(like, **escape_clause)),
            ).order_by(Task.data_prevista.asc().nullslast()).limit(25).all()
        if result_type in {"all", "question"}:
            results["questions"] = Question.query.filter(
                Question.user_id == current_user.id,
                Question.enunciado.ilike(like, **escape_clause),
            ).order_by(Question.created_at.desc()).limit(25).all()

    total_results = sum(len(items) for items in results.values())
    return render_template(
        "search.html",
        search_query=search_query,
        result_type=result_type,
        results=results,
        total_results=total_results,
    )


@main_bp.route("/weekly-goal", methods=["POST"])
@login_required
def weekly_goal():
    hours = request.form.get("weekly_goal_hours", type=float)
    if hours is None or hours < 1 or hours > 80:
        flash("Informe uma meta semanal entre 1 e 80 horas.", "warning")
        return redirect(url_for("main.dashboard"))

    current_user.weekly_goal_minutes = int(round(hours * 60))
    db.session.commit()
    flash("Meta semanal atualizada.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/sessions/<int:id>/toggle", methods=["POST"])
@login_required
def toggle_session(id):
    study_session = get_user_session(id)
    study_session.completed = not study_session.completed
    study_session.completed_at = datetime.now(UTC) if study_session.completed else None
    
    if study_session.completed:
        study_session.status = "completed"
    else:
        study_session.status = "scheduled"

    if study_session.completed:
        from app.planner.spaced_repetition import calculate_next_review_date

        task = Task.query.filter_by(
            user_id=current_user.id,
            subject_id=study_session.subject_id,
        ).order_by(Task.data_criacao.desc()).first()

        if task:
            correct_pct = None
            total_questions = 0

            if hasattr(task, 'correct_pct'):
                correct_pct = task.correct_pct
                total_questions = getattr(task, 'total_questions', 1)

            next_review = calculate_next_review_date(
                correct_pct=correct_pct,
                total_questions=total_questions,
            )
            if next_review:
                task.next_review_date = next_review

        if study_session.topic_id:
            from app.performance.services import update_knowledge_state
            update_knowledge_state(
                user_id=current_user.id,
                topic_id=study_session.topic_id,
                commit=False,
            )

    db.session.commit()
    status = "concluída" if study_session.completed else "reaberta"
    flash(f"Sessão {status}.", "success")
    return redirect(_safe_next_url())


@main_bp.route("/health")
def health():
    return {"status": "ok"}, 200
