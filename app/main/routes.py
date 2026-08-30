from datetime import UTC, datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.main import main_bp
from app.main.stats import build_dashboard_stats
from app.models import StudySession


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
    session = StudySession.query.filter_by(user_id=current_user.id, id=id).first_or_404()
    session.completed = not session.completed
    session.completed_at = datetime.now(UTC) if session.completed else None
    db.session.commit()
    status = "concluída" if session.completed else "reaberta"
    flash(f"Sessão {status}.", "success")
    return redirect(_safe_next_url())


@main_bp.route("/health")
def health():
    return {"status": "ok"}, 200
