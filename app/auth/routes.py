from flask import render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.auth import auth_bp
from app.auth.forms import RegistrationForm, LoginForm, ProfileForm, ChangePasswordForm
from app.models import User


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("Este email já está cadastrado.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(nome=form.nome.data.strip(), email=email)
        user.set_senha(form.senha.data)
        db.session.add(user)
        db.session.commit()
        flash("Conta criada com sucesso! Faça login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_senha(form.senha.data):
            login_user(user)
            flash("Bem-vindo de volta!", "success")
            return redirect(url_for("main.dashboard"))
        flash("Email ou senha inválidos.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
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
