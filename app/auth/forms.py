from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


class RegistrationForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField(
        "Senha", validators=[DataRequired(), Length(min=8, max=128)]
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
        "Nova senha", validators=[DataRequired(), Length(min=8, max=128)]
    )
    confirmar_nova_senha = PasswordField(
        "Confirmar nova senha",
        validators=[DataRequired(), EqualTo("nova_senha", message="As senhas não conferem.")],
    )
    submit = SubmitField("Alterar senha")
