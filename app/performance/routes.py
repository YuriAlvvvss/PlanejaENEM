"""
Performance routes for PlanejaENEM 3.0.

Displays performance dashboard with knowledge state, mastery scores,
recommendations, and trend analysis.
"""

import logging

from flask import current_app, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.performance import performance_bp
from app.performance.statistics import (
    get_area_stats,
    get_best_worst_subject,
    get_difficulty_stats,
    get_overall_stats,
    get_recent_performance,
    get_subject_stats,
    get_topic_stats,
)
from app.performance.services import (
    get_primary_recommendation,
    get_secondary_recommendations,
    get_subject_mastery_map,
    get_topic_detail,
    get_user_knowledge_summary,
    update_all_knowledge_states,
)

logger = logging.getLogger(__name__)


@performance_bp.route("/")
@login_required
def overview():
    overall = get_overall_stats(current_user.id)
    subject_stats = get_subject_stats(current_user.id)
    topic_stats = get_topic_stats(current_user.id)
    difficulty_stats = get_difficulty_stats(current_user.id)
    recent = get_recent_performance(current_user.id)
    best, worst = get_best_worst_subject(current_user.id)
    area_stats = get_area_stats(current_user.id)

    knowledge_summary = get_user_knowledge_summary(current_user.id)
    subject_mastery = get_subject_mastery_map(current_user.id)

    primary_rec = get_primary_recommendation(current_user.id)
    secondary_recs = get_secondary_recommendations(current_user.id, limit=3)

    feedback = None
    if knowledge_summary.get("has_data"):
        try:
            from app.ai.feedback_generator import FeedbackGenerator, PerformanceData

            weak_points = [
                t.get("topic_name", "")
                for t in knowledge_summary.get("weakest_topics", [])
                if t.get("topic_name")
            ]
            strong_points = [
                t.get("topic_name", "")
                for t in knowledge_summary.get("strongest_topics", [])
                if t.get("topic_name")
            ]

            recent_performance = [
                a.get("correta", False)
                for a in recent.get("attempts", [])
            ]
            recent_performance = [
                1.0 if p else 0.0 for p in recent_performance
            ]

            historical_performance = [
                s.get("accuracy", 0) / 100.0 for s in subject_stats
            ]

            trend_map = {
                "improving": "melhorando",
                "declining": "piorando",
                "stable": "estavel",
            }

            perf_data = PerformanceData(
                accuracy=overall.get("accuracy", 0) / 100.0,
                mastery=knowledge_summary.get("average_mastery", 0.0),
                confidence=knowledge_summary.get("average_mastery", 0.0),
                trend=trend_map.get(
                    knowledge_summary.get("overall_trend", "stable"), "estavel"
                ),
                strong_points=strong_points,
                weak_points=weak_points,
                recent_performance=recent_performance if recent_performance else [0.0],
                historical_performance=historical_performance if historical_performance else [0.0],
            )
            feedback = current_app.feedback_generator.generate(perf_data)
        except Exception as exc:
            logger.warning("Erro ao gerar feedback: %s", exc)
            feedback = None

    return render_template(
        "performance/overview.html",
        overall=overall,
        subject_stats=subject_stats,
        topic_stats=topic_stats,
        difficulty_stats=difficulty_stats,
        recent=recent,
        best_subject=best,
        worst_subject=worst,
        area_stats=area_stats,
        knowledge_summary=knowledge_summary,
        subject_mastery=subject_mastery,
        primary_recommendation=primary_rec,
        secondary_recommendations=secondary_recs,
        feedback=feedback,
    )


@performance_bp.route("/refresh")
@login_required
def refresh_knowledge():
    update_all_knowledge_states(current_user.id)
    return redirect(url_for("performance.overview"))
