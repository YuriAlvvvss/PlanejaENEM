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
    TwoFactorConfirmForm,
    TwoFactorDisableForm,
    TwoFactorSetupForm,
    TwoFactorVerifyForm,
)
from app.auth.two_factor import (
    PENDING_EXP_KEY,
    PENDING_REMEMBER_KEY,
    PENDING_SESSION_KEY,
    PENDING_TTL_SECONDS,
    SETUP_CODES_KEY,
    SETUP_SECRET_KEY,
    provisioning_uri,
    twofa_enabled,
    verify_totp,
)
from app.extensions import db, limiter
from app.models import (
    PasswordResetToken,
    Question,
    QuestionAttempt,
    StudyPlan,
    StudySession,
    Subject,
    Task,
    Topic,
    TwoFactorBackupCode,
    User,
)
from app.subjects.catalog import provision_subjects

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
            db.session.flush()
            provision_subjects(user.id)
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
            # 2FA: senha ok mas segundo fator pendente -> sem login_user ainda.
            if (
                twofa_enabled()
                and getattr(user, "totp_enabled", False)
                and user.totp_secret
            ):
                _regenerate_session()
                session[PENDING_SESSION_KEY] = user.id
                session[PENDING_EXP_KEY] = time.time() + PENDING_TTL_SECONDS
                session[PENDING_REMEMBER_KEY] = True
                session.modified = True
                flash("Informe o código do seu app autenticador.", "info")
                return redirect(url_for("auth.two_factor_verify"))
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
    disable_form = TwoFactorDisableForm()

    if profile_form.submit.data and profile_form.validate_on_submit():
        if not current_user.check_senha(profile_form.senha_atual.data):
            flash("Senha atual incorreta.", "danger")
            return render_template(
                "auth/profile.html",
                profile_form=profile_form,
                password_form=password_form,
                disable_form=disable_form,
                twofa_enabled=twofa_enabled(),
            )

        email = profile_form.email.data.strip().lower()
        if email != current_user.email and User.query.filter_by(email=email).first():
            flash("Este e-mail já está cadastrado.", "danger")
            return render_template(
                "auth/profile.html",
                profile_form=profile_form,
                password_form=password_form,
                disable_form=disable_form,
                twofa_enabled=twofa_enabled(),
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
                disable_form=disable_form,
                twofa_enabled=twofa_enabled(),
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
        disable_form=disable_form,
        twofa_enabled=twofa_enabled(),
    )


@auth_bp.route("/notification-preference", methods=["POST"])
@login_required
def notification_preference():
    """Toggle on-site de notificações (preferência não sensível, sem senha).

    E-mail real fica atrás de flag futura; por ora controla o digest on-site.
    """
    opt_in = request.form.get("email_opt_in") in {"1", "true", "on", "yes"}
    current_user.email_opt_in = opt_in
    db.session.commit()
    flash(
        "Notificações ativadas." if opt_in else "Notificações desativadas.",
        "success",
    )
    return redirect(url_for("auth.profile"))


@auth_bp.route("/appearance", methods=["POST"])
@login_required
def appearance():
    """Salva preferências de aparência/lista (não sensíveis, sem senha)."""
    theme = (request.form.get("theme") or "").strip().lower()
    density = (request.form.get("density") or "").strip().lower()
    default_status = (request.form.get("default_task_status") or "").strip().lower()
    if theme in {"light", "dark"}:
        current_user.theme = theme
    if density in {"comfortable", "compact"}:
        current_user.density = density
    if default_status in {"all", "pending", "done"}:
        current_user.default_task_status = default_status
    db.session.commit()
    flash("Aparência atualizada.", "success")
    return redirect(url_for("auth.profile"))


def _twofa_guard():
    from flask import abort

    if not twofa_enabled():
        abort(404)


def _pending_user():
    user_id = session.get(PENDING_SESSION_KEY)
    exp = session.get(PENDING_EXP_KEY)
    if not user_id or not exp or time.time() > exp:
        session.pop(PENDING_SESSION_KEY, None)
        session.pop(PENDING_EXP_KEY, None)
        session.pop(PENDING_REMEMBER_KEY, None)
        return None
    return db.session.get(User, int(user_id))


@auth_bp.route("/two-factor/verify", methods=["GET", "POST"])
@limiter.limit("10/minute")
def two_factor_verify():
    _twofa_guard()
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    user = _pending_user()
    if user is None:
        flash("Sessão expirada. Faça login novamente.", "warning")
        return redirect(url_for("auth.login"))
    lock_key = f"2fa:{user.id}"
    if _is_locked(lock_key):
        session.pop(PENDING_SESSION_KEY, None)
        session.pop(PENDING_EXP_KEY, None)
        session.pop(PENDING_REMEMBER_KEY, None)
        flash("Muitas tentativas. Faça login novamente.", "warning")
        return redirect(url_for("auth.login"))

    form = TwoFactorVerifyForm()
    if form.validate_on_submit():
        code = (form.codigo.data or "").strip().replace(" ", "")
        ok = bool(user.totp_secret) and verify_totp(user.totp_secret, code)
        used_backup = None
        if not ok:
            for backup in TwoFactorBackupCode.query.filter_by(
                user_id=user.id, used=False
            ).all():
                if backup.check_code(code):
                    ok = True
                    used_backup = backup
                    break
        if ok:
            try:
                if used_backup is not None:
                    used_backup.used = True
                remember = bool(session.get(PENDING_REMEMBER_KEY, True))
                session.pop(PENDING_SESSION_KEY, None)
                session.pop(PENDING_EXP_KEY, None)
                session.pop(PENDING_REMEMBER_KEY, None)
                _clear_failed_attempts(lock_key)
                _regenerate_session()
                login_user(user, remember=remember)
                session.permanent = True
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Erro ao verificar. Tente novamente.", "danger")
                return render_template("auth/two_factor_verify.html", form=form)
            current_app.logger.info("User logged in with 2FA")
            flash("Bem-vindo de volta!", "success")
            return redirect(url_for("main.dashboard"))
        _register_failed_attempt(lock_key)
        flash("Código inválido.", "danger")
    return render_template("auth/two_factor_verify.html", form=form)


@auth_bp.route("/two-factor/setup", methods=["GET", "POST"])
@login_required
@limiter.limit("10/minute")
def two_factor_setup():
    _twofa_guard()
    if current_user.totp_enabled:
        flash("2FA já está ativo.", "info")
        return redirect(url_for("auth.profile"))
    form = TwoFactorSetupForm()
    if form.validate_on_submit():
        if not current_user.check_senha(form.senha_atual.data):
            flash("Senha atual incorreta.", "danger")
            return render_template(
                "auth/two_factor_setup.html",
                form=form,
                secret=None,
                codes=None,
                uri=None,
            )
        import pyotp

        secret = pyotp.random_base32()
        codes = [TwoFactorBackupCode.generate_code() for _ in range(10)]
        session[SETUP_SECRET_KEY] = secret
        session[SETUP_CODES_KEY] = codes
        session.modified = True
        confirm_form = TwoFactorConfirmForm()
        return render_template(
            "auth/two_factor_setup.html",
            form=form,
            secret=secret,
            codes=codes,
            uri=provisioning_uri(secret, current_user.email),
            confirm_form=confirm_form,
        )
    return render_template(
        "auth/two_factor_setup.html", form=form, secret=None, codes=None, uri=None
    )


@auth_bp.route("/two-factor/setup/confirm", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def two_factor_confirm():
    _twofa_guard()
    if current_user.totp_enabled:
        flash("2FA já está ativo.", "info")
        return redirect(url_for("auth.profile"))
    secret = session.get(SETUP_SECRET_KEY)
    codes = session.get(SETUP_CODES_KEY)
    if not secret or not codes:
        flash("Gere a chave primeiro.", "warning")
        return redirect(url_for("auth.two_factor_setup"))
    form = TwoFactorConfirmForm()
    if form.validate_on_submit():
        if not current_user.check_senha(form.senha_atual.data):
            flash("Senha atual incorreta.", "danger")
            return redirect(url_for("auth.two_factor_setup"))
        if not verify_totp(secret, form.codigo.data):
            flash("Código inválido. Confira o app e tente novamente.", "danger")
            return redirect(url_for("auth.two_factor_setup"))
        try:
            current_user.totp_secret = secret
            current_user.totp_enabled = True
            for code in codes:
                db.session.add(
                    TwoFactorBackupCode(
                        user_id=current_user.id,
                        code_hash=TwoFactorBackupCode.hash_code(code),
                    )
                )
            db.session.commit()
            session.pop(SETUP_SECRET_KEY, None)
            session.pop(SETUP_CODES_KEY, None)
        except Exception:
            db.session.rollback()
            flash("Erro ao ativar. Tente novamente.", "danger")
            return redirect(url_for("auth.two_factor_setup"))
        flash("2FA ativado com sucesso! Guarde seus backup codes.", "success")
        return redirect(url_for("auth.profile"))
    flash("Verifique os campos.", "warning")
    return redirect(url_for("auth.two_factor_setup"))


@auth_bp.route("/two-factor/disable", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def two_factor_disable():
    _twofa_guard()
    if not current_user.totp_enabled:
        return redirect(url_for("auth.profile"))
    form = TwoFactorDisableForm()
    if form.validate_on_submit() and current_user.check_senha(form.senha_atual.data):
        code = (form.codigo.data or "").strip().replace(" ", "")
        ok = bool(current_user.totp_secret) and verify_totp(
            current_user.totp_secret, code
        )
        used_backup = None
        if not ok:
            for backup in TwoFactorBackupCode.query.filter_by(
                user_id=current_user.id, used=False
            ).all():
                if backup.check_code(code):
                    ok = True
                    used_backup = backup
                    break
        if ok:
            try:
                current_user.totp_secret = None
                current_user.totp_enabled = False
                TwoFactorBackupCode.query.filter_by(
                    user_id=current_user.id, used=False
                ).update({"used": True})
                if used_backup is not None:
                    used_backup.used = True
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Erro ao desativar. Tente novamente.", "danger")
                return redirect(url_for("auth.profile"))
            flash("2FA desativado.", "info")
            return redirect(url_for("auth.profile"))
    flash("Senha ou código incorretos.", "danger")
    return redirect(url_for("auth.profile"))


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

    from app.ai.models import AIUsage
    from app.assessment.models import Assessment, AssessmentQuestion
    from app.performance.models import KnowledgeState

    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    plans = StudyPlan.query.filter_by(user_id=current_user.id).all()
    sessions = StudySession.query.filter_by(user_id=current_user.id).all()
    topics = Topic.query.filter_by(user_id=current_user.id).all()
    questions = Question.query.filter_by(user_id=current_user.id).all()
    attempts = QuestionAttempt.query.filter_by(user_id=current_user.id).all()
    knowledge_states = KnowledgeState.query.filter_by(user_id=current_user.id).all()
    assessments = Assessment.query.filter_by(user_id=current_user.id).all()
    assessment_questions = AssessmentQuestion.query.filter_by(
        user_id=current_user.id
    ).all()
    ai_usage = AIUsage.query.filter_by(user_id=current_user.id).all()

    data = {
        "user": {
            "nome": current_user.nome,
            "email": current_user.email,
            "weekly_goal_minutes": current_user.weekly_goal_minutes,
            "email_opt_in": bool(current_user.email_opt_in),
            "theme": current_user.theme,
            "density": current_user.density,
            "default_task_status": current_user.default_task_status,
            "totp_enabled": bool(current_user.totp_enabled),
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
        "topics": [
            {
                "nome": t.nome,
                "subject": t.subject.nome if t.subject else None,
            }
            for t in topics
        ],
        "questions": [
            {
                "enunciado": q.enunciado,
                "subject": q.subject.nome if q.subject else None,
                "topic": q.topic.nome if q.topic else None,
                "resposta_correta": q.resposta_correta,
                "dificuldade": q.dificuldade,
                "ano": q.ano,
                "fonte": q.fonte,
            }
            for q in questions
        ],
        "question_attempts": [
            {
                "question_id": a.question_id,
                "resposta": a.resposta,
                "correta": a.correta,
                "tempo_segundos": a.tempo_segundos,
                "attempted_at": a.attempted_at.isoformat() if a.attempted_at else None,
            }
            for a in attempts
        ],
        "knowledge_states": [
            {
                "subject_id": ks.subject_id,
                "topic_id": ks.topic_id,
                "mastery_score": ks.mastery_score,
                "confidence_score": ks.confidence_score,
                "questions_answered": ks.questions_answered,
                "trend": ks.trend,
            }
            for ks in knowledge_states
        ],
        "assessments": [a.to_dict() for a in assessments],
        "assessment_questions": [aq.to_dict() for aq in assessment_questions],
        "ai_usage": [
            {
                "feature": u.feature,
                "model": u.model,
                "total_tokens": u.total_tokens,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in ai_usage
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

        from app.ai.models import AIUsage
        from app.assessment.models import Assessment, AssessmentQuestion
        from app.performance.models import KnowledgeState

        user_id = current_user.id
        try:
            # Ordem filha -> pai para respeitar FKs em qualquer backend.
            AssessmentQuestion.query.filter_by(user_id=user_id).delete()
            QuestionAttempt.query.filter_by(user_id=user_id).delete()
            Assessment.query.filter_by(user_id=user_id).delete()
            Question.query.filter_by(user_id=user_id).delete()
            KnowledgeState.query.filter_by(user_id=user_id).delete()
            StudySession.query.filter_by(user_id=user_id).delete()
            StudyPlan.query.filter_by(user_id=user_id).delete()
            Topic.query.filter_by(user_id=user_id).delete()
            Task.query.filter_by(user_id=user_id).delete()
            AIUsage.query.filter_by(user_id=user_id).delete()
            PasswordResetToken.query.filter_by(user_id=user_id).delete()
            TwoFactorBackupCode.query.filter_by(user_id=user_id).delete()
            Subject.query.filter_by(user_id=user_id).delete()

            user = db.session.get(User, user_id)
            logout_user()
            db.session.delete(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Account deletion failed")
            flash("Erro ao excluir conta. Tente novamente.", "danger")
            return render_template("auth/delete_account.html")

        current_app.logger.info("Account deleted")
        flash("Conta excluída com sucesso.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/delete_account.html")
