"""
Performance routes for PlanejaENEM.

Displays performance dashboard with statistics from question attempts.
"""

from flask import render_template
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
    )
