"""
Models de avaliação adaptativa - PlanejaENEM 5.0.

Define Assessment (sessão de avaliação) e AssessmentQuestion (cada questão
apresentada durante a avaliação). O Decision Engine controla a dificuldade
e seleção de assuntos, enquanto a IA gera apenas o conteúdo das questões.
"""

from datetime import datetime, timezone

from app.extensions import db


class Assessment(db.Model):
    """
    Sessão de avaliação adaptativa.

    Cada assessment representa um ciclo completo de avaliação do aluno,
    com questões de dificuldade variável selecionadas pelo Decision Engine.
    """

    __tablename__ = "assessments"
    __table_args__ = (
        db.Index("idx_assessment_user_id", "user_id"),
        db.Index("idx_assessment_status", "status"),
        db.Index("idx_assessment_user_status", "user_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    # Configuração da avaliação
    target_questions = db.Column(db.Integer, nullable=False, default=10)
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id"), nullable=True, index=True
    )

    # Estado atual
    status = db.Column(
        db.String(20), nullable=False, default="active"
    )  # active, completed, abandoned
    current_question_number = db.Column(db.Integer, nullable=False, default=0)
    current_difficulty = db.Column(db.Float, nullable=False, default=3.0)

    # Resultados parciais
    correct_count = db.Column(db.Integer, nullable=False, default=0)
    wrong_count = db.Column(db.Integer, nullable=False, default=0)
    total_time_seconds = db.Column(db.Integer, nullable=False, default=0)

    # Timestamps
    started_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relacionamentos
    user = db.relationship(
        "User", backref=db.backref("assessments", lazy=True, cascade="all, delete-orphan")
    )
    subject = db.relationship("Subject", backref=db.backref("assessments", lazy=True))
    questions = db.relationship(
        "AssessmentQuestion",
        backref="assessment",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="AssessmentQuestion.order",
    )

    @property
    def accuracy(self) -> float:
        """Percentual de acerto (0-100)."""
        total = self.correct_count + self.wrong_count
        if total <= 0:
            return 0.0
        return round((self.correct_count / total) * 100, 2)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def questions_remaining(self) -> int:
        return max(0, self.target_questions - self.current_question_number)

    def __repr__(self):
        return (
            f"<Assessment id={self.id} user={self.user_id} "
            f"status={self.status} progress={self.current_question_number}/{self.target_questions}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "target_questions": self.target_questions,
            "subject_id": self.subject_id,
            "status": self.status,
            "current_question_number": self.current_question_number,
            "current_difficulty": self.current_difficulty,
            "correct_count": self.correct_count,
            "wrong_count": self.wrong_count,
            "accuracy": self.accuracy,
            "total_time_seconds": self.total_time_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "questions_remaining": self.questions_remaining,
        }


class AssessmentQuestion(db.Model):
    """
    Cada questão apresentada durante uma avaliação adaptativa.

    Registra a ordem, dificuldade alvo, resposta do aluno, correção,
    tempo gasto e a questão utilizada (Question ou gerada por IA).
    """

    __tablename__ = "assessment_questions"
    __table_args__ = (
        db.Index("idx_aq_assessment_id", "assessment_id"),
        db.Index("idx_aq_user_id", "user_id"),
        db.Index("idx_aq_question_id", "question_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(
        db.Integer, db.ForeignKey("assessments.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    # Ordem e configuração
    order = db.Column(db.Integer, nullable=False)
    target_difficulty = db.Column(db.Float, nullable=False)
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id"), nullable=True
    )
    topic_id = db.Column(
        db.Integer, db.ForeignKey("topics.id"), nullable=True
    )

    # Questão utilizada (pode ser do banco ou gerada por IA)
    question_id = db.Column(
        db.Integer, db.ForeignKey("questions.id"), nullable=True, index=True
    )
    # Dados da questão gerada por IA (quando não usada do banco)
    generated_question_data = db.Column(db.Text, nullable=True)

    # Resposta do aluno
    resposta = db.Column(db.String(1), nullable=True)  # A-E
    correta = db.Column(db.Boolean, nullable=True)
    tempo_segundos = db.Column(db.Integer, nullable=True)

    # Contexto da decisão (por que esta questão foi escolhida)
    decision_reason = db.Column(db.Text, nullable=True)

    # Timestamps
    presented_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    answered_at = db.Column(db.DateTime, nullable=True)

    # Relacionamentos
    user = db.relationship("User", backref=db.backref("assessment_questions", lazy=True))
    subject = db.relationship("Subject", backref=db.backref("assessment_questions", lazy=True))
    topic = db.relationship("Topic", backref=db.backref("assessment_questions", lazy=True))
    question = db.relationship(
        "Question", backref=db.backref("assessment_questions", lazy=True)
    )

    @property
    def response_time(self) -> float | None:
        """Tempo de resposta em segundos."""
        return self.tempo_segundos

    def __repr__(self):
        return (
            f"<AssessmentQuestion assessment={self.assessment_id} "
            f"order={self.order} correct={self.correta}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "assessment_id": self.assessment_id,
            "order": self.order,
            "target_difficulty": self.target_difficulty,
            "subject_id": self.subject_id,
            "topic_id": self.topic_id,
            "question_id": self.question_id,
            "resposta": self.resposta,
            "correta": self.correta,
            "tempo_segundos": self.tempo_segundos,
            "presented_at": self.presented_at.isoformat() if self.presented_at else None,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
        }
