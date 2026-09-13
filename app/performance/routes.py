"""
Performance routes for PlanejaENEM 3.0.

Displays performance dashboard with knowledge state, mastery scores,
recommendations, and trend analysis.
"""

import logging
from datetime import datetime, timedelta, timezone

from flask import current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.areas import AREA_LABELS
from app.models import Subject
from app.performance import performance_bp
from app.performance.statistics import (
    get_area_stats,
    get_best_worst_subject,
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
    from app.performance.models import KnowledgeState

    filter_subject = request.args.get("subject", type=int)
    filter_area = (request.args.get("area") or "all").strip().lower()
    if filter_area not in set(AREA_LABELS.keys()) | {"all"}:
        filter_area = "all"
    filter_periodo = (request.args.get("periodo") or "all").strip().lower()
    if filter_periodo not in {"all", "7d", "30d", "90d"}:
        filter_periodo = "all"

    # Subject válido e do usuário; inválido = ignorado (URL compartilhável nunca 500).
    subject = None
    if filter_subject:
        subject = Subject.query.filter_by(id=filter_subject, user_id=current_user.id).first()
        if subject is None:
            filter_subject = None

    since = None
    if filter_periodo in {"7d", "30d", "90d"}:
        days = {"7d": 7, "30d": 30, "90d": 90}[filter_periodo]
        since = datetime.now(timezone.utc) - timedelta(days=days)

    overall = get_overall_stats(current_user.id, since=since)
    subject_stats = get_subject_stats(current_user.id, since=since)
    topic_stats = get_topic_stats(current_user.id, subject_id=filter_subject, since=since)
    recent = get_recent_performance(current_user.id, since=since, subject_id=filter_subject)

    # Filtro de área aplica-se sobre listas já calculadas (sem nova query por matéria).
    if filter_area != "all":
        area_subject_ids = {
            s.id
            for s in Subject.query.filter_by(user_id=current_user.id, area=filter_area).all()
        }
        subject_stats = [s for s in subject_stats if s.get("subject_id") in area_subject_ids]
        # topic_stats não carrega subject_id direto; filtra pelo nome via subjects da área.
        area_subject_names = {
            s.nome
            for s in Subject.query.filter_by(user_id=current_user.id, area=filter_area).all()
        }
        topic_stats = [t for t in topic_stats if t.get("subject_nome") in area_subject_names]
        if subject_stats:
            overall_total = sum(s.get("total", 0) for s in subject_stats)
            overall_correct = sum(s.get("correct", 0) for s in subject_stats)
            overall = {
                "total": overall_total,
                "correct": overall_correct,
                "wrong": overall_total - overall_correct,
                "accuracy": round((overall_correct / overall_total) * 100) if overall_total else 0,
            }
    if filter_subject:
        subject_stats = [s for s in subject_stats if s.get("subject_id") == filter_subject]
        if subject_stats:
            s = subject_stats[0]
            overall = {
                "total": s.get("total", 0),
                "correct": s.get("correct", 0),
                "wrong": s.get("wrong", 0),
                "accuracy": s.get("accuracy", 0),
            }
        else:
            overall = {"total": 0, "correct": 0, "wrong": 0, "accuracy": 0}

    if subject_stats:
        best, worst = subject_stats[0], subject_stats[-1]
    else:
        best, worst = None, None
    area_stats = get_area_stats(current_user.id, since=since)

    # Mapa topic_id -> KnowledgeState para drill-down (1 query, sem N+1).
    ks_map = {
        ks.topic_id: ks
        for ks in KnowledgeState.query.filter_by(user_id=current_user.id).all()
    }
    for t in topic_stats:
        ks = ks_map.get(t.get("topic_id"))
        t["mastery"] = round(ks.mastery_score, 1) if ks else None
        t["trend"] = ks.trend if ks else None
    for s in subject_stats:
        ks_list = [ks for ks in ks_map.values() if ks.subject_id == s.get("subject_id")]
        s["mastery"] = (
            round(sum(k.mastery_score for k in ks_list) / len(ks_list), 1) if ks_list else None
        )

    # Métricas úteis: tempo médio + evolução (cumulativa) para gráfico.
    times = [a.get("tempo_segundos") for a in recent.get("attempts", []) if a.get("tempo_segundos") is not None]
    avg_time = round(sum(times) / len(times), 1) if times else None
    evolution = []
    correct_run = 0
    ordered = list(reversed(recent.get("attempts", [])))
    for i, a in enumerate(ordered, start=1):
        if a.get("correta"):
            correct_run += 1
        evolution.append(round((correct_run / i) * 100))

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    area_options = list(AREA_LABELS.items())

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
        recent=recent,
        best_subject=best,
        worst_subject=worst,
        area_stats=area_stats,
        knowledge_summary=knowledge_summary,
        subject_mastery=subject_mastery,
        primary_recommendation=primary_rec,
        secondary_recommendations=secondary_recs,
        feedback=feedback,
        subjects=subjects,
        area_options=area_options,
        filter_subject=filter_subject,
        filter_area=filter_area,
        filter_periodo=filter_periodo,
        avg_time=avg_time,
        evolution=evolution,
    )


@performance_bp.route("/refresh", methods=["POST"])
@login_required
def refresh_knowledge():
    update_all_knowledge_states(current_user.id)
    from flask import flash

    flash("Desempenho atualizado.", "success")
    return redirect(url_for("performance.overview"))
