import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import auth_bp
from app.auth.forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    ProfileForm,
    RegistrationForm,
    ResetPasswordForm,
)
from app.extensions import db, limiter
from app.models import PasswordResetToken, StudyPlan, StudySession, Subject, Task, User

MAX_FAILED_ATTEMPTS = 5
LOCK_WINDOW_SECONDS = 300


def _get_failed_login_store():
    store = current_app.config.setdefault("_failed_login_attempts", defaultdict(list))
    return store


def _prune_attempts(attempts):
    current_time = time.time()
    return [timestamp for timestamp in attempts if current_time - timestamp < LOCK_WINDOW_SECONDS]


def _is_locked(key):
    store = _get_failed_login_store()
    attempts = _prune_attempts(store.get(key, []))
    store[key] = attempts
    return len(attempts) >= MAX_FAILED_ATTEMPTS


def _register_failed_attempt(key):
    store = _get_failed_login_store()
    attempts = _prune_attempts(store.get(key, []))
    attempts.append(time.time())
    store[key] = attempts


def _clear_failed_attempts(key):
    store = _get_failed_login_store()
    store.pop(key, None)


def _mask_email(email):
    """Mask email for logging: a***@example.com"""
    if not email or "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"


def _regenerate_session():
    """Regenerate session to prevent session fixation attacks."""
    user_id = session.get("_user_id")
    remember = session.get("remember")
    session.clear()
    if user_id:
        session["_user_id"] = user_id
    if remember:
        session["remember"] = remember
    session.modified = True


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5/minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            current_app.logger.warning("Registration attempt with existing email")
            flash("Este email já está cadastrado.", "danger")
            return render_template("auth/register.html", form=form)

        try:
            user = User(nome=form.nome.data.strip(), email=email)
            user.set_senha(form.senha.data)
            db.session.add(user)
            db.session.commit()
            current_app.logger.info("New user registered")
            flash("Conta criada com sucesso! Faça login.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error: {str(e)}")
            flash("Erro ao criar conta. Tente novamente.", "danger")

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10/minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    email = (form.email.data or "").strip().lower()
    remote_ip = request.remote_addr or "unknown"

    if _is_locked(remote_ip) or _is_locked(email):
        flash("Muitas tentativas de login. Tente novamente em alguns minutos.", "warning")
        return render_template("auth/login.html", form=form)

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_senha(form.senha.data):
            _clear_failed_attempts(remote_ip)
            _clear_failed_attempts(email)
            _regenerate_session()
            login_user(user, remember=True)
            session.permanent = True
            current_app.logger.info("User logged in")
            flash("Bem-vindo de volta!", "success")
            return redirect(url_for("main.dashboard"))

        current_app.logger.warning("Failed login attempt")
        _register_failed_attempt(remote_ip)
        _register_failed_attempt(email)
        flash("Email ou senha inválidos.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    _regenerate_session()
    logout_user()
    session.clear()
    current_app.logger.info("User logged out")
    flash("Você saiu da conta.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile_form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()

    if profile_form.submit.data and profile_form.validate_on_submit():
        if not current_user.check_senha(profile_form.senha_atual.data):
            flash("Senha atual incorreta.", "danger")
            return render_template(
                "auth/profile.html",
                profile_form=profile_form,
                password_form=password_form,
            )

        email = profile_form.email.data.strip().lower()
        if email != current_user.email and User.query.filter_by(email=email).first():
            flash("Este e-mail já está cadastrado.", "danger")
            return render_template(
                "auth/profile.html",
                profile_form=profile_form,
                password_form=password_form,
            )

        current_user.nome = profile_form.nome.data.strip()
        current_user.email = email
        db.session.commit()
        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("auth.profile"))

    if password_form.submit.data and password_form.validate_on_submit():
        if not current_user.check_senha(password_form.senha_atual.data):
            flash("Senha atual incorreta.", "danger")
            return render_template(
                "auth/profile.html",
                profile_form=profile_form,
                password_form=password_form,
            )

        current_user.set_senha(password_form.nova_senha.data)
        db.session.commit()
        _regenerate_session()
        login_user(current_user, remember=True)
        flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("auth.profile"))

    return render_template(
        "auth/profile.html",
        profile_form=profile_form,
        password_form=password_form,
    )


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3/minute")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({"used": True})

            token = PasswordResetToken.generate_token()
            reset = PasswordResetToken(
                user_id=user.id,
                token_hash=PasswordResetToken.hash_token(token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            db.session.add(resim)
            db.session.commit()

            current_app.logger.info("Password reset requested")

        flash(
            "Se este email estiver cadastrado, você receberá um link de recuperação.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5/minute")
def reset_password(token):
    reset = PasswordResetToken.query.filter_by(used=False).first()
    if not reset or not reset.check_token(token):
        flash("Link de recuperação inválido ou expirado.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if not reset.is_valid():
        flash("Link de recuperação expirado. Solicite um novo.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = db.session.get(User, reset.user_id)
        if user:
            user.set_senha(form.nova_senha.data)
            reset.used = True
            db.session.commit()
            _regenerate_session()
            current_app.logger.info("Password reset completed")
            flash("Senha redefinida com sucesso! Faça login.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/privacy")
@login_required
def privacy():
    return render_template("auth/privacy.html")


@auth_bp.route("/export-data")
@login_required
def export_data():
    import json

    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    plans = StudyPlan.query.filter_by(user_id=current_user.id).all()
    sessions = StudySession.query.filter_by(user_id=current_user.id).all()

    data = {
        "user": {
            "nome": current_user.nome,
            "email": current_user.email,
            "weekly_goal_minutes": current_user.weekly_goal_minutes,
            "data_criacao": current_user.data_criacao.isoformat() if current_user.data_criacao else None,
        },
        "subjects": [
            {
                "nome": s.nome,
                "cor": s.cor,
                "prioridade": s.prioridade,
                "dificuldade": s.dificuldade,
                "area": s.area,
            }
            for s in subjects
        ],
        "tasks": [
            {
                "titulo": t.titulo,
                "descricao": t.descricao,
                "subject": t.subject.nome if t.subject else None,
                "data_prevista": t.data_prevista.isoformat() if t.data_prevista else None,
                "concluida": t.concluida,
                "prioridade": t.prioridade,
            }
            for t in tasks
        ],
        "study_plans": [
            {
                "exam_date": p.exam_date.isoformat(),
                "daily_minutes": p.daily_minutes,
                "available_days": p.available_days,
                "available_hours": p.available_hours,
                "generated_at": p.generated_at.isoformat() if p.generated_at else None,
            }
            for p in plans
        ],
        "study_sessions": [
            {
                "subject": s.subject.nome if s.subject else None,
                "session_date": s.session_date.isoformat(),
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "duration_minutes": s.duration_minutes,
                "completed": s.completed,
                "session_type": s.session_type,
            }
            for s in sessions
        ],
    }

    from flask import Response

    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=planejaenem_dados.json"},
    )


@auth_bp.route("/delete-account", methods=["GET", "POST"])
@login_required
def delete_account():
    if request.method == "POST":
        password = request.form.get("senha", "")
        if not current_user.check_senha(password):
            flash("Senha incorreta. Conta não excluída.", "danger")
            return render_template("auth/delete_account.html")

        PasswordResetToken.query.filter_by(user_id=current_user.id).delete()
        StudySession.query.filter_by(user_id=current_user.id).delete()
        StudyPlan.query.filter_by(user_id=current_user.id).delete()
        Task.query.filter_by(user_id=current_user.id).delete()
        Subject.query.filter_by(user_id=current_user.id).delete()

        user = db.session.get(User, current_user.id)
        logout_user()
        db.session.delete(user)
        db.session.commit()

        current_app.logger.info("Account deleted")
        flash("Conta excluída com sucesso.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/delete_account.html")
