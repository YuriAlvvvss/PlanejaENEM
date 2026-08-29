import re

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


def validate_password_strength(form, field):
    value = field.data or ""
    if len(value) < 8:
        raise ValidationError("A senha deve ter pelo menos 8 caracteres.")
    if not re.search(r"[A-Z]", value):
        raise ValidationError("A senha deve conter pelo menos uma letra maiúscula.")
    if not re.search(r"[a-z]", value):
        raise ValidationError("A senha deve conter pelo menos uma letra minúscula.")
    if not re.search(r"\d", value):
        raise ValidationError("A senha deve conter pelo menos um número.")


class RegistrationForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField(
        "Senha",
        validators=[DataRequired(), Length(min=8, max=128), validate_password_strength],
    )
    confirmar_senha = PasswordField(
        "Confirmar Senha",
        validators=[DataRequired(), EqualTo("senha", message="As senhas não conferem.")],
    )
    submit = SubmitField("Registrar")

    def validate_email(self, field):
        from app.models import User

        email = field.data.strip().lower()
        if User.query.filter_by(email=email).first():
            raise ValidationError("Este e-mail já está cadastrado.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")


class ProfileForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Salvar alterações")

    def validate_email(self, field):
        from app.models import User

        email = field.data.strip().lower()
        current_email = self.obj.email if getattr(self, "obj", None) else None
        if email != current_email and User.query.filter_by(email=email).first():
            raise ValidationError("Este e-mail já está cadastrado.")


class ChangePasswordForm(FlaskForm):
    senha_atual = PasswordField("Senha atual", validators=[DataRequired()])
    nova_senha = PasswordField(
        "Nova senha",
        validators=[DataRequired(), Length(min=8, max=128), validate_password_strength],
    )
    confirmar_nova_senha = PasswordField(
        "Confirmar nova senha",
        validators=[DataRequired(), EqualTo("nova_senha", message="As senhas não conferem.")],
    )
    submit = SubmitField("Alterar senha")
