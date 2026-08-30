"""
Services do planner - PlanejaENEM Adaptive Planner v2.

Orquestra as operações de planejamento, integrando scoring,
revisão espaçada, scheduler e modelos.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from app.extensions import db
from app.models import StudyPlan, StudySession, Subject, Task, User
from app.planner.scoring import calculate_subject_need_score
from app.planner.spaced_repetition import (
    calculate_next_review_date,
    classify_performance,
    get_review_status,
    calculate_overdue_days,
)
from app.planner.scheduler import (
    calculate_time_allocation,
    distribute_sessions,
    generate_session_schedule,
    get_study_phase,
    recommend_study_type,
    reschedule_missed_sessions,
)
from app.planner.validators import (
    validate_available_days,
    validate_available_hours,
    validate_daily_minutes,
    validate_exam_date,
    validate_subject_settings,
)


def get_subject_performance(subject_id: int, user_id: int) -> dict:
    """
    Calcula o desempenho do aluno em uma matéria baseado em tarefas concluídas.

    Retorna dict com:
    - correct_pct: percentual de aproveitamento (None se sem dados)
    - total_tasks: total de tarefas
    - completed_tasks: tarefas concluídas
    - performance_level: classificação textual
    """
    tasks = Task.query.filter_by(
        user_id=user_id,
        subject_id=subject_id,
        concluida=True,
    ).all()

    total = len(tasks)
    completed = total

    correct_pct = None
    performance_level = "medium"

    if total > 0:
        avg_priority = 0
        high_priority_count = 0
        for task in tasks:
            if task.prioridade == "alta":
                high_priority_count += 1
            elif task.prioridade == "media":
                avg_priority += 1

        if total > 0:
            completion_rate = (high_priority_count / total) * 100 if total else 0
            correct_pct = max(0, min(100, 100 - completion_rate * 0.3))

        performance_level = classify_performance(correct_pct, total)

    return {
        "correct_pct": correct_pct,
        "total_tasks": total,
        "completed_tasks": completed,
        "performance_level": performance_level,
    }


def get_subject_need_data(
    subject: Subject,
    user_id: int,
    exam_date: date,
    today: Optional[date] = None,
) -> dict:
    """
    Coleta todos os dados necessários para calcular o score de uma matéria.
    """
    today = today or date.today()
    days_until_exam = max(0, (exam_date - today).days)

    performance = get_subject_performance(subject.id, user_id)

    pending_tasks = Task.query.filter_by(
        user_id=user_id,
        subject_id=subject.id,
        concluida=False,
    ).count()

    total_tasks = Task.query.filter_by(
        user_id=user_id,
        subject_id=subject.id,
    ).count()

    last_review = None
    overdue_reviews = 0

    completed_tasks = Task.query.filter_by(
        user_id=user_id,
        subject_id=subject.id,
        concluida=True,
    ).filter(Task.next_review_date.isnot(None)).all()

    for task in completed_tasks:
        if task.next_review_date:
            if last_review is None or task.next_review_date > last_review:
                last_review = task.next_review_date

            status = get_review_status(task.next_review_date, today)
            if status == "overdue":
                overdue_reviews += 1

    score_data = calculate_subject_need_score(
        priority=subject.prioridade,
        difficulty=subject.dificuldade,
        correct_pct=performance["correct_pct"],
        total_questions=performance["total_tasks"],
        days_until_exam=days_until_exam,
        last_review_date=last_review,
        overdue_reviews=overdue_reviews,
        pending_tasks=pending_tasks,
        total_tasks=total_tasks,
        today=today,
    )

    return {
        "subject_id": subject.id,
        "subject_name": subject.nome,
        "area": subject.area,
        "score": score_data["total"],
        "components": score_data["components"],
        "performance": performance,
        "pending_tasks": pending_tasks,
        "total_tasks": total_tasks,
        "overdue_reviews": overdue_reviews,
        "last_review_date": last_review,
        "days_until_exam": days_until_exam,
    }


def generate_adaptive_plan(
    user_id: int,
    days: list[str],
    hours: list[str],
    daily_minutes: int,
    exam_date: date,
    subject_settings: dict,
    today: Optional[date] = None,
) -> dict:
    """
    Gera um plano de estudo adaptativo completo.

    Retorna dict com:
    - sessions: lista de sessões geradas
    - explanations: dict com explicações por matéria
    - summary: resumo do plano
    """
    today = today or date.today()

    subjects = Subject.query.filter_by(user_id=user_id).order_by(Subject.nome).all()
    if not subjects:
        return {
            "sessions": [],
            "explanations": {},
            "summary": {"total_sessions": 0, "total_minutes": 0},
        }

    subject_scores = []
    explanations = {}

    for subject in subjects:
        settings = subject_settings.get(subject.id, {"priority": 3, "difficulty": 3})

        merged_subject = subject
        if settings.get("priority") != subject.prioridade:
            merged_subject = type(subject)()
            merged_subject.id = subject.id
            merged_subject.nome = subject.nome
            merged_subject.cor = subject.cor
            merged_subject.prioridade = settings["priority"]
            merged_subject.dificuldade = settings.get("difficulty", subject.dificuldade)
            merged_subject.area = subject.area
            merged_subject.user_id = user_id

        need_data = get_subject_need_data(merged_subject, user_id, exam_date, today)

        subject_scores.append({
            "subject_id": subject.id,
            "score": need_data["score"],
            "area": need_data["area"],
            "performance": need_data["performance"]["performance_level"],
            "components": need_data["components"],
        })

        explanations[subject.id] = {
            "name": subject.nome,
            "score": need_data["score"],
            "components": need_data["components"],
            "performance": need_data["performance"],
            "pending_tasks": need_data["pending_tasks"],
            "overdue_reviews": need_data["overdue_reviews"],
            "reasons": _build_explanation_reasons(need_data),
        }

    user = db.session.get(User, user_id)
    weekly_goal = getattr(user, "weekly_goal_minutes", 600) if user else 600

    allocation_result = calculate_time_allocation(
        subject_scores, weekly_goal, len(days)
    )

    subject_allocations = allocation_result["allocations"]

    subject_data_for_scheduler = {}
    for s in subject_scores:
        sid = s["subject_id"]
        if sid in subject_allocations:
            subject_data_for_scheduler[sid] = {
                "score": s["score"],
                "area": s["area"],
                "performance": s["performance"],
            }

    schedule = generate_session_schedule(
        days, hours, daily_minutes, exam_date, today
    )

    generated_sessions = distribute_sessions(
        schedule, subject_allocations, subject_data_for_scheduler,
        daily_minutes,
    )

    for session in generated_sessions:
        for s in subject_scores:
            if s["subject_id"] == session["subject_id"]:
                session["priority_score"] = int(s["score"])
                break

    total_minutes = sum(s.get("duration_minutes", 0) for s in generated_sessions)

    summary = {
        "total_sessions": len(generated_sessions),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 1),
        "phase": get_study_phase(max(0, (exam_date - today).days)),
        "days_until_exam": (exam_date - today).days,
        "subjects_count": len(subjects),
    }

    return {
        "sessions": generated_sessions,
        "explanations": explanations,
        "allocations": allocation_result["allocations"],
        "summary": summary,
    }


def _build_explanation_reasons(need_data: dict) -> list[str]:
    """Constrói lista de motivos para a prioridade da matéria."""
    reasons = []
    components = need_data.get("components", {})
    performance = need_data.get("performance", {})

    if components.get("performance", 50) > 60:
        pct = performance.get("correct_pct")
        if pct is not None:
            reasons.append(f"Desempenho: {pct:.0f}%")
        else:
            reasons.append("Desempenho: sem dados suficientes")

    if components.get("difficulty", 50) > 60:
        reasons.append("Dificuldade: alta")

    if components.get("priority", 50) > 60:
        reasons.append("Prioridade: alta")

    if need_data.get("overdue_reviews", 0) > 0:
        reasons.append(f"{need_data['overdue_reviews']} revisão(ões) atrasada(s)")

    if need_data.get("pending_tasks", 0) > 0:
        reasons.append(f"{need_data['pending_tasks']} tarefa(s) pendente(s)")

    if components.get("exam_proximity", 50) > 70:
        reasons.append("ENEM se aproxima")

    if components.get("revision", 50) > 70:
        reasons.append("Faz tempo desde a última revisão")

    return reasons


def detect_missed_sessions(user_id: int, today: Optional[date] = None) -> list[StudySession]:
    """
    Detecta sessões que foram perdidas (data passada e não concluída).
    """
    today = today or date.today()

    missed = StudySession.query.filter(
        StudySession.user_id == user_id,
        StudySession.session_date < today,
        StudySession.completed == False,  # noqa: E712
        StudySession.manual_override == False,  # noqa: E712
    ).all()

    return missed


def replan_after_missed_sessions(
    user_id: int,
    today: Optional[date] = None,
) -> dict:
    """
    Replaneja após detectar sessões perdidas.

    Retorna dict com:
    - missed_count: número de sessões perdidas
    - rescheduled_count: número de sessões reagendadas
    - updated_plan: plano atualizado (se existir)
    """
    today = today or date.today()

    missed = detect_missed_sessions(user_id, today)

    if not missed:
        return {
            "missed_count": 0,
            "rescheduled_count": 0,
            "updated_plan": None,
        }

    for session in missed:
        session.completed = True
        session.completed_at = datetime.now(timezone.utc)
        session.notes = (session.notes or "") + " [Reagendado automaticamente - sessão perdida]"

    missed_data = []
    for session in missed:
        missed_data.append({
            "subject_id": session.subject_id,
            "session_date": session.session_date,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "duration_minutes": session.duration_minutes,
            "priority_score": session.priority_score,
        })

    plan = StudyPlan.query.filter_by(user_id=user_id).order_by(
        StudyPlan.generated_at.desc()
    ).first()

    rescheduled = []
    if plan:
        existing_sessions = []
        for s in plan.sessions:
            existing_sessions.append({
                "session_date": s.session_date,
                "start_time": s.start_time.strftime("%H:%M") if isinstance(s.start_time, time) else str(s.start_time),
                "end_time": s.end_time.strftime("%H:%M") if isinstance(s.end_time, time) else str(s.end_time),
                "duration_minutes": s.duration_minutes,
            })

        rescheduled = reschedule_missed_sessions(
            missed_data,
            existing_sessions,
            plan.days_list,
            plan.hours_list,
            plan.daily_minutes,
            plan.exam_date,
            today,
        )

        for rs in rescheduled:
            subject_id = rs.get("subject_id")
            start_time = rs.get("start_time")
            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, "%H:%M").time()
            end_time = rs.get("end_time")
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, "%H:%M").time()

            new_session = StudySession(
                plan_id=plan.id,
                user_id=user_id,
                subject_id=subject_id,
                session_date=rs.get("session_date", today),
                start_time=start_time,
                end_time=end_time,
                duration_minutes=rs.get("duration_minutes", 60),
                priority_score=rs.get("priority_score", 0),
                manual_override=False,
                notes="[Reagendado automaticamente]",
            )
            db.session.add(new_session)

    db.session.commit()

    return {
        "missed_count": len(missed),
        "rescheduled_count": len(rescheduled),
        "updated_plan": plan,
    }


def get_diagnostics(user_id: int) -> dict:
    """
    Gera diagnóstico inicial do desempenho do aluno por área.
    """
    subjects = Subject.query.filter_by(user_id=user_id).all()

    if not subjects:
        return {
            "areas": {},
            "overall": 0,
            "has_data": False,
        }

    from app.areas import infer_area, area_label

    area_stats = {}
    for subject in subjects:
        area = subject.area
        if not area or area == "outro":
            area = infer_area(subject.nome)

        performance = get_subject_performance(subject.id, user_id)

        if area not in area_stats:
            area_stats[area] = {
                "label": area_label(area),
                "total_questions": 0,
                "correct_pct_sum": 0,
                "subjects_count": 0,
                "subject_details": [],
            }

        area_stats[area]["subjects_count"] += 1
        area_stats[area]["total_questions"] += performance["total_tasks"]

        if performance["correct_pct"] is not None:
            area_stats[area]["correct_pct_sum"] += performance["correct_pct"]

        area_stats[area]["subject_details"].append({
            "name": subject.nome,
            "total_tasks": performance["total_tasks"],
            "correct_pct": performance["correct_pct"],
            "performance_level": performance["performance_level"],
        })

    areas = {}
    total_pct = 0
    area_count = 0

    for area_key, stats in area_stats.items():
        if stats["total_questions"] > 0 and stats["subjects_count"] > 0:
            avg_pct = stats["correct_pct_sum"] / stats["subjects_count"]
        else:
            avg_pct = None

        areas[area_key] = {
            "label": stats["label"],
            "average_percent": round(avg_pct, 1) if avg_pct is not None else None,
            "total_questions": stats["total_questions"],
            "subjects": stats["subjects_count"],
            "subject_details": stats["subject_details"],
        }

        if avg_pct is not None:
            total_pct += avg_pct
            area_count += 1

    overall = round(total_pct / area_count, 1) if area_count > 0 else 0

    return {
        "areas": areas,
        "overall": overall,
        "has_data": area_count > 0,
    }


def process_planner_request(
    user_id: int,
    form_data: dict,
    subjects: list,
    today: Optional[date] = None,
) -> tuple[dict, list[str]]:
    """
    Processa a requisição completa do planner.

    Retorna (resultado, erros).
    """
    today = today or date.today()
    all_errors = []

    days_raw = form_data.getlist("available_days") if hasattr(form_data, "getlist") else form_data.get("available_days", [])
    valid_days, day_errors = validate_available_days(days_raw)
    all_errors.extend(day_errors)

    hours_raw = form_data.get("available_hours", "")
    valid_hours, hour_errors = validate_available_hours(hours_raw)
    all_errors.extend(hour_errors)

    daily_minutes_raw = form_data.get("daily_minutes", 60)
    valid_minutes, minute_errors = validate_daily_minutes(daily_minutes_raw)
    all_errors.extend(minute_errors)

    exam_date_raw = form_data.get("exam_date", "")
    valid_exam_date, exam_errors = validate_exam_date(exam_date_raw, today)
    all_errors.extend(exam_errors)

    subject_settings, settings_errors = validate_subject_settings(subjects, form_data)
    all_errors.extend(settings_errors)

    if all_errors:
        return {"sessions": [], "explanations": {}, "summary": {}}, all_errors

    if not valid_days or not valid_hours or valid_exam_date is None:
        if not valid_days:
            all_errors.append("Selecione pelo menos um dia da semana.")
        if not valid_hours:
            all_errors.append("Informe horários válidos.")
        if valid_exam_date is None:
            all_errors.append("Informe a data da prova.")
        return {"sessions": [], "explanations": {}, "summary": {}}, all_errors

    result = generate_adaptive_plan(
        user_id=user_id,
        days=valid_days,
        hours=valid_hours,
        daily_minutes=valid_minutes,
        exam_date=valid_exam_date,
        subject_settings=subject_settings,
        today=today,
    )

    if not result["sessions"]:
        all_errors.append(
            "Não foi possível gerar um cronograma. Verifique sua disponibilidade."
        )

    return result, all_errors
