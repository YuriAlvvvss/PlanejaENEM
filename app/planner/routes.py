from datetime import UTC, date, datetime, timedelta

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import StudyPlan, StudySession, Subject
from app.planner import planner_bp


DAYS_ORDER = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
DAY_LABELS = {
    "seg": "Segunda",
    "ter": "Terça",
    "qua": "Quarta",
    "qui": "Quinta",
    "sex": "Sexta",
    "sab": "Sábado",
    "dom": "Domingo",
}


def parse_available_days(raw_days):
    if isinstance(raw_days, list):
        values = raw_days
    elif raw_days:
        values = [item.strip().lower() for item in str(raw_days).split(",") if item.strip()]
    else:
        values = []
    return [day for day in DAYS_ORDER if day in values]


def parse_available_hours(raw_hours):
    if not raw_hours:
        return []
    slots = []
    for chunk in str(raw_hours).split(","):
        slot = chunk.strip()
        if not slot:
            continue
        if "-" in slot:
            slots.append(slot)
    return slots


def parse_subject_priority(subjects, form):
    values = {}
    for subject in subjects:
        priority = form.get(f"priority_{subject.id}")
        difficulty = form.get(f"difficulty_{subject.id}")

        if isinstance(priority, str):
            normalized = priority.strip().lower()
            priority_map = {"baixa": 1, "media": 3, "alta": 5}
            priority_value = priority_map.get(normalized, int(normalized) if normalized.isdigit() else 1)
        else:
            priority_value = int(priority or 1)

        if isinstance(difficulty, str):
            normalized = difficulty.strip().lower()
            difficulty_value = int(normalized) if normalized.isdigit() else 3
        else:
            difficulty_value = int(difficulty or 3)

        values[subject.id] = {
            "priority": priority_value,
            "difficulty": difficulty_value,
        }
    return values


def generate_plan_for_user(user_id, days, hours, daily_minutes, exam_date, subject_settings):
    subjects = Subject.query.filter_by(user_id=user_id).order_by(Subject.nome).all()
    if not subjects:
        return []

    day_slots = []
    for slot in hours:
        bit = slot.split("-")
        if len(bit) != 2:
            continue
        start = bit[0].strip()
        end = bit[1].strip()
        try:
            start_t = datetime.strptime(start, "%H:%M").time()
            end_t = datetime.strptime(end, "%H:%M").time()
            if end_t <= start_t:
                continue
            day_slots.append((start_t, end_t))
        except ValueError:
            continue

    if not day_slots:
        return []

    day_aliases = {
        "mon": "seg",
        "tue": "ter",
        "wed": "qua",
        "thu": "qui",
        "fri": "sex",
        "sat": "sab",
        "sun": "dom",
    }
    selected_days = [
        day
        for day in DAYS_ORDER
        if day in days or any(alias == day for alias in (item.lower()[:3] for item in days))
    ]
    if not selected_days:
        return []

    sessions = []
    exam_date_obj = datetime.strptime(str(exam_date), "%Y-%m-%d").date() if isinstance(exam_date, str) else exam_date

    sorted_subjects = sorted(
        subjects,
        key=lambda subject: (
            -(subject.priority_score if hasattr(subject, "priority_score") else 1),
            -(subject_settings.get(subject.id, {}).get("priority", 1) * 10 + subject_settings.get(subject.id, {}).get("difficulty", 1)),
            subject.nome,
        ),
    )

    date_cursor = date.today()
    if exam_date_obj >= date_cursor:
        date_cursor = date_cursor
    else:
        date_cursor = date.today()

    session_counter = 0
    while date_cursor <= exam_date_obj:
        weekday = date_cursor.strftime("%a").lower()[:3]
        normalized_weekday = day_aliases.get(weekday, weekday)
        if normalized_weekday in selected_days:
            for start_t, end_t in day_slots:
                if session_counter >= max(1, len(subjects) * 2):
                    break
                chosen_subject = sorted_subjects[session_counter % len(sorted_subjects)]
                duration = max(
                    30,
                    min(
                        daily_minutes,
                        int(
                            (datetime.combine(date.today(), end_t)
                             - datetime.combine(date.today(), start_t)).total_seconds()
                            // 60
                        ),
                    ),
                )
                session_start = start_t
                session_end = (datetime.combine(date.today(), start_t) + timedelta(minutes=duration)).time()

                sessions.append(
                    {
                        "subject_id": chosen_subject.id,
                        "session_date": date_cursor,
                        "start_time": session_start,
                        "end_time": session_end,
                        "duration_minutes": duration,
                        "priority_score": int(subject_settings.get(chosen_subject.id, {}).get("priority", 1) * 10),
                    }
                )
                session_counter += 1
        date_cursor += timedelta(days=1)

    return sessions


@planner_bp.route("/", methods=["GET", "POST"])
@login_required
def planner():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.nome).all()
    existing_plan = StudyPlan.query.filter_by(user_id=current_user.id).order_by(StudyPlan.generated_at.desc()).first()

    if request.method == "POST":
        available_days = request.form.getlist("available_days")
        available_hours = request.form.get("available_hours", "")
        daily_minutes = request.form.get("daily_minutes", 60, type=int)
        exam_date = request.form.get("exam_date")
        subject_settings = parse_subject_priority(subjects, request.form)

        if not exam_date:
            flash("Informe a data da prova antes de gerar o cronograma.", "warning")
            return render_template(
                "planner/planner.html",
                subjects=subjects,
                active_plan=existing_plan,
                mode="form",
            )

        generated_sessions = generate_plan_for_user(
            current_user.id,
            parse_available_days(available_days),
            parse_available_hours(available_hours),
            daily_minutes,
            exam_date,
            subject_settings,
        )

        if not generated_sessions:
            flash("Não foi possível gerar um cronograma com a disponibilidade informada. Ajuste dias e horários.", "warning")
            return render_template(
                "planner/planner.html",
                subjects=subjects,
                active_plan=existing_plan,
                mode="form",
            )

        plan = StudyPlan(
            user_id=current_user.id,
            exam_date=datetime.strptime(exam_date, "%Y-%m-%d").date(),
            daily_minutes=daily_minutes,
            available_days=",".join(parse_available_days(available_days)),
            available_hours=available_hours,
            generated_at=datetime.now(UTC),
        )
        db.session.add(plan)
        db.session.flush()

        for session in generated_sessions:
            db.session.add(
                StudySession(
                    plan_id=plan.id,
                    user_id=current_user.id,
                    subject_id=session["subject_id"],
                    session_date=session["session_date"],
                    start_time=session["start_time"],
                    end_time=session["end_time"],
                    duration_minutes=session["duration_minutes"],
                    priority_score=session["priority_score"],
                )
            )

        db.session.commit()
        flash("Cronograma gerado com sucesso!", "success")
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
    plan = StudyPlan.query.filter_by(user_id=current_user.id, id=id).first_or_404()
    if plan.sessions:
        for session in plan.sessions:
            db.session.delete(session)
    db.session.delete(plan)
    db.session.commit()
    flash("Cronograma regenerado. Ajuste os dados e gere um novo planejamento.", "info")
    return redirect(url_for("planner.planner"))


@planner_bp.route("/<int:id>/manual", methods=["POST"])
@login_required
def update_manual(id):
    session = StudySession.query.filter_by(user_id=current_user.id, id=id).first_or_404()
    session.manual_override = True
    session.notes = request.form.get("notes", session.notes)
    if request.form.get("subject_id"):
        session.subject_id = int(request.form.get("subject_id"))
    db.session.commit()
    flash("Sessão atualizada manualmente.", "success")
    return redirect(url_for("planner.planner"))
