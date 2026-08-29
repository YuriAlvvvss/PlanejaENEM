import time
from collections import defaultdict

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import auth_bp
from app.auth.forms import ChangePasswordForm, LoginForm, ProfileForm, RegistrationForm
from app.extensions import db
from app.models import User

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


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            current_app.logger.warning(f"Registration attempt with existing email: {email}")
            flash("Este email já está cadastrado.", "danger")
            return render_template("auth/register.html", form=form)

        try:
            user = User(nome=form.nome.data.strip(), email=email)
            user.set_senha(form.senha.data)
            db.session.add(user)
            db.session.commit()
            current_app.logger.info(f"New user registered: {email}")
            flash("Conta criada com sucesso! Faça login.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error for {email}: {str(e)}")
            flash("Erro ao criar conta. Tente novamente.", "danger")

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
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
            login_user(user, remember=True)
            session.permanent = True
            current_app.logger.info(f"User logged in: {email}")
            flash("Bem-vindo de volta!", "success")
            return redirect(url_for("main.dashboard"))

        current_app.logger.warning(f"Failed login attempt for: {email}")
        _register_failed_attempt(remote_ip)
        _register_failed_attempt(email)
        flash("Email ou senha inválidos.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    email = current_user.email
    logout_user()
    session.clear()
    current_app.logger.info(f"User logged out: {email}")
    flash("Você saiu da conta.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile_form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()

    if profile_form.submit.data and profile_form.validate_on_submit():
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
        flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("auth.profile"))

    return render_template(
        "auth/profile.html",
        profile_form=profile_form,
        password_form=password_form,
    )
