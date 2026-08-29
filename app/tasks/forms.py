from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class TaskForm(FlaskForm):
    titulo = StringField("Titulo", validators=[DataRequired(), Length(max=200)])
    descricao = TextAreaField("Descricao", validators=[Optional()])
    subject_id = SelectField("Materia", coerce=int, validators=[DataRequired()])
    data_prevista = DateField("Data Prevista", validators=[Optional()], format="%Y-%m-%d")
    prioridade = SelectField(
        "Prioridade",
        choices=[("baixa", "Baixa"), ("media", "Media"), ("alta", "Alta")],
        validators=[DataRequired()],
    )
    concluida = BooleanField("Concluida")
    submit = SubmitField("Salvar")
