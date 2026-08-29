from flask import render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.auth import auth_bp
from app.auth.forms import RegistrationForm, LoginForm
from app.models import User


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Este email ja esta cadastrado.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(nome=form.nome.data, email=form.email.data)
        user.set_senha(form.senha.data)
        db.session.add(user)
        db.session.commit()
        flash("Conta criada com sucesso! Faca login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_senha(form.senha.data):
            login_user(user)
            flash("Bem-vindo de volta!", "success")
            return redirect(url_for("main.dashboard"))
        flash("Email ou senha invalidos.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Voce saiu da conta.", "info")
    return redirect(url_for("auth.login"))
