import re

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

from app.areas import ENEM_AREAS


class SubjectForm(FlaskForm):
    nome = StringField("Nome da Matéria", validators=[DataRequired(), Length(max=100)])
    cor = StringField("Cor (hex)", validators=[DataRequired(), Length(min=7, max=7)])
    prioridade = SelectField(
        "Prioridade",
        choices=[("1", "1 - baixa"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5 - alta")],
        default="3",
        coerce=int,
    )
    dificuldade = SelectField(
        "Dificuldade",
        choices=[("1", "1 - fácil"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5 - alta")],
        default="3",
        coerce=int,
    )
    area = SelectField("Área do ENEM", choices=ENEM_AREAS, default="outro")
    submit = SubmitField("Salvar")

    def validate_nome(self, field):
        field.data = field.data.strip()
        if not field.data:
            raise ValidationError("Informe um nome válido para a matéria.")

    def validate_cor(self, field):
        value = field.data.strip()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise ValidationError("Use uma cor válida em hexadecimal, como #3B82F6.")
        field.data = value
