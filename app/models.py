from datetime import date, datetime, timezone
import secrets

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    weekly_goal_minutes = db.Column(db.Integer, nullable=False, default=600)
    data_criacao = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    subjects = db.relationship("Subject", backref="user", lazy=True, cascade="all, delete-orphan")
    tasks = db.relationship("Task", backref="user", lazy=True, cascade="all, delete-orphan")
    study_plans = db.relationship(
        "StudyPlan", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    study_sessions = db.relationship(
        "StudySession", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    topics = db.relationship("Topic", backref="user", lazy=True, cascade="all, delete-orphan")
    questions = db.relationship("Question", backref="user", lazy=True, cascade="all, delete-orphan")
    question_attempts = db.relationship(
        "QuestionAttempt", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(256), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref="reset_tokens")

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token):
        from werkzeug.security import generate_password_hash
        return generate_password_hash(token, method="sha256")

    def check_token(self, token):
        return check_password_hash(self.token_hash, token)

    def is_valid(self):
        return not self.used and datetime.now(timezone.utc) < self.expires_at.replace(tzinfo=timezone.utc)

    def __repr__(self):
        return f"<PasswordResetToken user_id={self.user_id}>"


class Subject(db.Model):
    __tablename__ = "subjects"
    __table_args__ = (
        db.Index("idx_subject_user_id", "user_id"),
        db.Index("idx_subject_user_nome", "user_id", "nome"),
        db.UniqueConstraint("user_id", "nome", name="uq_subject_user_nome"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cor = db.Column(db.String(7), nullable=False, default="#007bff")
    prioridade = db.Column(db.Integer, nullable=False, default=1)
    dificuldade = db.Column(db.Integer, nullable=False, default=3)
    area = db.Column(db.String(20), nullable=False, default="outro")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    data_criacao = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    tasks = db.relationship("Task", backref="subject", lazy=True, cascade="all, delete-orphan")

    @property
    def total_tasks(self):
        return len(self.tasks)

    @property
    def completed_tasks(self):
        return sum(1 for t in self.tasks if t.concluida)

    @property
    def progress_percent(self):
        total = self.total_tasks
        if total == 0:
            return 0
        return round((self.completed_tasks / total) * 100)

    @property
    def priority_score(self):
        return max(1, int(self.prioridade or 1)) * (int(self.dificuldade or 1) + 1)

    @property
    def area_label(self):
        from app.areas import area_label, infer_area

        key = self.area if self.area and self.area != "outro" else infer_area(self.nome)
        return area_label(key)

    def __repr__(self):
        return f"<Subject {self.nome}>"


class Task(db.Model):
    __tablename__ = "tasks"
    __table_args__ = (
        db.Index("idx_task_user_id", "user_id"),
        db.Index("idx_task_subject_id", "subject_id"),
        db.Index("idx_task_user_concluida", "user_id", "concluida"),
        db.Index("idx_task_user_data_prevista", "user_id", "data_prevista"),
        db.Index("idx_task_prioridade", "prioridade"),
    )

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    data_prevista = db.Column(db.Date, nullable=True)
    concluida = db.Column(db.Boolean, default=False, nullable=False)
    prioridade = db.Column(
        db.String(10), nullable=False, default="media"
    )  # baixa, media, alta
    completed_at = db.Column(db.DateTime, nullable=True)
    next_review_date = db.Column(db.Date, nullable=True)
    data_criacao = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Task {self.titulo}>"


class StudyPlan(db.Model):
    __tablename__ = "study_plans"
    __table_args__ = (
        db.Index("idx_study_plan_user_id", "user_id"),
        db.Index("idx_study_plan_exam_date", "exam_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    exam_date = db.Column(db.Date, nullable=False)
    daily_minutes = db.Column(db.Integer, nullable=False, default=90)
    available_days = db.Column(db.String(200), nullable=False, default="seg,qua,sex")
    available_hours = db.Column(db.Text, nullable=False, default="08:00-10:00")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_regenerated_at = db.Column(db.DateTime, nullable=True)

    sessions = db.relationship(
        "StudySession",
        backref="plan",
        lazy=True,
        cascade="all, delete-orphan",
    )

    @property
    def days_list(self):
        if not self.available_days:
            return []
        return [day.strip().lower() for day in self.available_days.split(",") if day.strip()]

    @property
    def hours_list(self):
        if not self.available_hours:
            return []
        return [slot.strip() for slot in self.available_hours.split(",") if slot.strip()]

    def __repr__(self):
        return f"<StudyPlan user_id={self.user_id} exam_date={self.exam_date}>"


class StudySession(db.Model):
    __tablename__ = "study_sessions"
    __table_args__ = (
        db.Index("idx_study_session_user_id", "user_id"),
        db.Index("idx_study_session_plan_id", "plan_id"),
        db.Index("idx_study_session_date", "session_date"),
        db.Index("idx_study_session_subject_id", "subject_id"),
    )

    SESSION_TYPES = ["teoria", "exercicios", "questoes_enem", "revisao", "simulado"]
    SESSION_STATUSES = ["scheduled", "completed", "missed", "rescheduled", "cancelled"]

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("study_plans.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=True, index=True)
    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    priority_score = db.Column(db.Integer, nullable=False, default=0)
    session_type = db.Column(db.String(20), nullable=False, default="teoria")
    status = db.Column(db.String(20), nullable=False, default="scheduled")
    manual_override = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)
    reason_codes = db.Column(db.Text, nullable=True)
    explanation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    subject = db.relationship("Subject", backref="study_sessions", lazy=True)

    @property
    def day_name(self):
        if not self.session_date:
            return "-"
        day_names = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        return day_names[self.session_date.weekday()]

    @property
    def is_missed(self):
        """Verifica se a sessão foi perdida (data passada e não concluída)."""
        if self.completed or self.manual_override:
            return False
        return self.session_date < date.today()

    def __repr__(self):
        return f"<StudySession {self.subject_id} {self.session_date} {self.start_time}>"


class Topic(db.Model):
    __tablename__ = "topics"
    __table_args__ = (
        db.Index("idx_topic_user_id", "user_id"),
        db.Index("idx_topic_subject_id", "subject_id"),
        db.Index("idx_topic_user_subject", "user_id", "subject_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    subject = db.relationship("Subject", backref=db.backref("topics", lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<Topic {self.nome}>"


class Question(db.Model):
    __tablename__ = "questions"
    __table_args__ = (
        db.Index("idx_question_user_id", "user_id"),
        db.Index("idx_question_subject_id", "subject_id"),
        db.Index("idx_question_topic_id", "topic_id"),
        db.Index("idx_question_user_subject", "user_id", "subject_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    enunciado = db.Column(db.Text, nullable=False)
    alternativa_a = db.Column(db.String(500), nullable=False)
    alternativa_b = db.Column(db.String(500), nullable=False)
    alternativa_c = db.Column(db.String(500), nullable=False)
    alternativa_d = db.Column(db.String(500), nullable=False)
    alternativa_e = db.Column(db.String(500), nullable=False)
    resposta_correta = db.Column(db.String(1), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    dificuldade = db.Column(db.Integer, nullable=False, default=3)
    ano = db.Column(db.Integer, nullable=True)
    fonte = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    subject = db.relationship("Subject", backref=db.backref("questions", lazy=True, cascade="all, delete-orphan"))
    topic = db.relationship("Topic", backref=db.backref("questions", lazy=True))

    def __repr__(self):
        return f"<Question {self.id}>"


class QuestionAttempt(db.Model):
    __tablename__ = "question_attempts"
    __table_args__ = (
        db.Index("idx_attempt_user_id", "user_id"),
        db.Index("idx_attempt_question_id", "question_id"),
        db.Index("idx_attempt_user_question", "user_id", "question_id"),
        db.Index("idx_attempt_attempted_at", "attempted_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False, index=True)
    resposta = db.Column(db.String(1), nullable=False)
    correta = db.Column(db.Boolean, nullable=False)
    tempo_segundos = db.Column(db.Integer, nullable=True)
    attempted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    question = db.relationship("Question", backref=db.backref("attempts", lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<QuestionAttempt user={self.user_id} q={self.question_id} correct={self.correta}>"
