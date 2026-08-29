from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError


class TaskForm(FlaskForm):
    titulo = StringField("Título", validators=[DataRequired(), Length(max=200)])
    descricao = TextAreaField("Descrição", validators=[Optional()])
    subject_id = SelectField("Matéria", coerce=int, validators=[DataRequired()])
    data_prevista = DateField("Data Prevista", validators=[Optional()], format="%Y-%m-%d")
    prioridade = SelectField(
        "Prioridade",
        choices=[("baixa", "Baixa"), ("media", "Media"), ("alta", "Alta")],
        validators=[DataRequired()],
    )
    concluida = BooleanField("Concluída")
    submit = SubmitField("Salvar")

    def validate_titulo(self, field):
        field.data = field.data.strip()
        if not field.data:
            raise ValidationError("Informe um título válido para a tarefa.")
