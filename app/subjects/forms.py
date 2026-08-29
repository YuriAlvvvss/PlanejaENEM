from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class SubjectForm(FlaskForm):
    nome = StringField("Nome da Matéria", validators=[DataRequired(), Length(max=100)])
    cor = StringField("Cor (hex)", validators=[DataRequired(), Length(min=7, max=7)])
    submit = SubmitField("Salvar")
