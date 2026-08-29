from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    data_criacao = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    subjects = db.relationship("Subject", backref="user", lazy=True, cascade="all, delete-orphan")
    tasks = db.relationship("Task", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


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
    data_criacao = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Task {self.titulo}>"
