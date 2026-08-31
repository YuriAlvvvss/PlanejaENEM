from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    IntegerField,
    RadioField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)


CORRETAS = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E")]
DIFICULDADES = [(str(i), str(i)) for i in range(1, 6)]


class TopicForm(FlaskForm):
    nome = StringField("Nome do Assunto", validators=[DataRequired(), Length(max=150)])
    subject_id = SelectField("Matéria", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Salvar")

    def validate_nome(self, field):
        field.data = field.data.strip()
        if not field.data:
            raise ValidationError("Informe um nome válido para o assunto.")


class QuestionForm(FlaskForm):
    enunciado = TextAreaField("Enunciado", validators=[DataRequired(), Length(max=5000)])
    alternativa_a = StringField("Alternativa A", validators=[DataRequired(), Length(max=500)])
    alternativa_b = StringField("Alternativa B", validators=[DataRequired(), Length(max=500)])
    alternativa_c = StringField("Alternativa C", validators=[DataRequired(), Length(max=500)])
    alternativa_d = StringField("Alternativa D", validators=[DataRequired(), Length(max=500)])
    alternativa_e = StringField("Alternativa E", validators=[DataRequired(), Length(max=500)])
    resposta_correta = SelectField("Resposta Correta", choices=CORRETAS, validators=[DataRequired()])
    subject_id = SelectField("Matéria", coerce=int, validators=[DataRequired()])
    topic_id = SelectField("Assunto", coerce=int, validators=[Optional()])
    dificuldade = SelectField("Dificuldade", choices=DIFICULDADES, default="3", coerce=int)
    ano = IntegerField("Ano", validators=[Optional(), NumberRange(min=2000, max=2030, message="Ano entre 2000 e 2030.")])
    fonte = StringField("Fonte", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Salvar")

    def validate_enunciado(self, field):
        field.data = field.data.strip()
        if not field.data:
            raise ValidationError("O enunciado é obrigatório.")

    def validate_resposta_correta(self, field):
        if field.data not in {"A", "B", "C", "D", "E"}:
            raise ValidationError("Resposta correta deve ser A, B, C, D ou E.")


class AnswerForm(FlaskForm):
    resposta = RadioField(
        "Sua resposta",
        choices=CORRETAS,
        validators=[DataRequired(message="Selecione uma alternativa.")],
    )
    tempo_segundos = IntegerField(
        "Tempo (segundos)",
        validators=[Optional(), NumberRange(min=0, max=7200, message="Tempo entre 0 e 7200 segundos.")],
    )
    submit = SubmitField("Confirmar Resposta")
