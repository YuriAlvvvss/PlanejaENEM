"""
Rotas do Decision Engine - PlanejaENEM 4.0.

Endpoints para recomendações, debug, simulação e histórico.
"""

from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash
from flask_login import current_user, login_required

from app.extensions import db
from app.models import StudyPlan, User
from app.decision_engine.engine import (
    generate_recommendations,
    get_current_recommendations,
    get_recommendation_history,
    build_debug_output,
)
from app.decision_engine.simulator import (
    simulate_plan,
    compare_plans,
    generate_comparison_report,
)
from app.decision_engine.types import WeeklyAvailability

decision_engine_bp = Blueprint(
    "decision_engine",
    __name__,
    url_prefix="/decision-engine",
)


def _get_availability_from_plan(plan: StudyPlan) -> WeeklyAvailability:
    """Extrai disponibilidade do plano existente."""
    user = db.session.get(User, plan.user_id)
    weekly_goal = user.weekly_goal_minutes if user else 600

    return WeeklyAvailability(
        days=plan.days_list,
        hours=plan.hours_list,
        daily_minutes=plan.daily_minutes,
        weekly_goal_minutes=weekly_goal,
    )


@decision_engine_bp.route("/recommendations", methods=["GET"])
@login_required
def recommendations():
    """
    Retorna recomendações atuais do decision engine.
    """
    today = date.today()

    plan = StudyPlan.query.filter_by(
        user_id=current_user.id,
        is_active=True,
    ).order_by(StudyPlan.generated_at.desc()).first()

    if plan is None:
        flash("Crie um plano de estudo primeiro.", "warning")
        return redirect(url_for("planner.index"))

    availability = _get_availability_from_plan(plan)

    result = generate_recommendations(
        user_id=current_user.id,
        exam_date=plan.exam_date,
        availability=availability,
        today=today,
    )

    return render_template(
        "decision_engine/recommendations.html",
        recommendations=result["recommendations"],
        summary=result["summary"],
        conflicts=result["conflicts"],
    )


@decision_engine_bp.route("/api/recommendations", methods=["GET"])
@login_required
def api_recommendations():
    """
    API endpoint para recomendações.
    Retorna JSON com recomendações ordenadas.
    """
    today = date.today()

    plan = StudyPlan.query.filter_by(
        user_id=current_user.id,
        is_active=True,
    ).order_by(StudyPlan.generated_at.desc()).first()

    if plan is None:
        return jsonify({"error": "Nenhum plano ativo encontrado"}), 404

    availability = _get_availability_from_plan(plan)

    result = generate_recommendations(
        user_id=current_user.id,
        exam_date=plan.exam_date,
        availability=availability,
        today=today,
    )

    return jsonify({
        "recommendations": [r.to_dict() for r in result["recommendations"]],
        "summary": result["summary"],
        "conflicts": [
            {
                "type": c.conflict_type.value,
                "severity": c.severity.value,
                "details": c.details,
            }
            for c in result["conflicts"]
        ],
    })


@decision_engine_bp.route("/debug", methods=["GET"])
@login_required
def debug():
    """
    Modo debug: mostra scores, pesos e reason codes detalhados.
    """
    today = date.today()

    plan = StudyPlan.query.filter_by(
        user_id=current_user.id,
        is_active=True,
    ).order_by(StudyPlan.generated_at.desc()).first()

    if plan is None:
        flash("Crie um plano de estudo primeiro.", "warning")
        return redirect(url_for("planner.index"))

    availability = _get_availability_from_plan(plan)

    result = generate_recommendations(
        user_id=current_user.id,
        exam_date=plan.exam_date,
        availability=availability,
        today=today,
    )

    debug_output = build_debug_output(result)

    return render_template(
        "decision_engine/debug.html",
        debug_output=debug_output,
        result=result,
    )


@decision_engine_bp.route("/simulate", methods=["GET", "POST"])
@login_required
def simulate():
    """
    Simula e compara planos de estudo.
    """
    if request.method == "GET":
        return render_template("decision_engine/simulate.html")

    plan_a_daily = request.form.get("plan_a_daily", 60, type=int)
    plan_a_weekly = request.form.get("plan_a_weekly", 420, type=int)
    plan_b_daily = request.form.get("plan_b_daily", 90, type=int)
    plan_b_weekly = request.form.get("plan_b_weekly", 630, type=int)

    today = date.today()

    plan = StudyPlan.query.filter_by(
        user_id=current_user.id,
        is_active=True,
    ).order_by(StudyPlan.generated_at.desc()).first()

    if plan is None:
        flash("Crie um plano de estudo primeiro.", "warning")
        return redirect(url_for("planner.index"))

    availability_a = WeeklyAvailability(
        days=plan.days_list,
        hours=plan.hours_list,
        daily_minutes=plan_a_daily,
        weekly_goal_minutes=plan_a_weekly,
    )

    availability_b = WeeklyAvailability(
        days=plan.days_list,
        hours=plan.hours_list,
        daily_minutes=plan_b_daily,
        weekly_goal_minutes=plan_b_weekly,
    )

    sim_a = simulate_plan(
        user_id=current_user.id,
        exam_date=plan.exam_date,
        availability=availability_a,
        plan_name="Plano A",
        today=today,
    )

    sim_b = simulate_plan(
        user_id=current_user.id,
        exam_date=plan.exam_date,
        availability=availability_b,
        plan_name="Plano B",
        today=today,
    )

    comparison = compare_plans(sim_a, sim_b)

    report = generate_comparison_report([sim_a, sim_b])

    return render_template(
        "decision_engine/simulation_result.html",
        simulation_a=sim_a,
        simulation_b=sim_b,
        comparison=comparison,
        report=report,
    )


@decision_engine_bp.route("/history", methods=["GET"])
@login_required
def history():
    """
    Histórico de recomendações e sessões.
    """
    limit = request.args.get("limit", 50, type=int)

    history_data = get_recommendation_history(current_user.id, limit)

    return render_template(
        "decision_engine/history.html",
        history=history_data,
    )
