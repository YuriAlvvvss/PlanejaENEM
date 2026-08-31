"""
Models de performance - PlanejaENEM 3.0.

Define o KnowledgeState (estado de conhecimento) do aluno por tópico.
Cada usuário possui seu próprio estado de conhecimento.
Nunca compartilhar KnowledgeState entre usuários.
"""

from datetime import datetime, timezone

from app.extensions import db


class KnowledgeState(db.Model):
    """
    Estado de conhecimento do aluno por tópico.

    Armazena métricas calculadas de domínio, confiança e tendência
    para cada combinação usuário + tópico.
    """

    __tablename__ = "knowledge_states"
    __table_args__ = (
        db.Index("idx_ks_user_id", "user_id"),
        db.Index("idx_ks_subject_id", "subject_id"),
        db.Index("idx_ks_topic_id", "topic_id"),
        db.Index("idx_ks_user_subject", "user_id", "subject_id"),
        db.Index("idx_ks_user_topic", "user_id", "topic_id"),
        db.UniqueConstraint(
            "user_id", "topic_id", name="uq_knowledge_state_user_topic"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True
    )
    topic_id = db.Column(
        db.Integer, db.ForeignKey("topics.id"), nullable=False, index=True
    )

    # Scores principais (0-100)
    mastery_score = db.Column(db.Float, nullable=False, default=0.0)
    confidence_score = db.Column(db.Float, nullable=False, default=0.0)

    # Contadores
    questions_answered = db.Column(db.Integer, nullable=False, default=0)
    questions_correct = db.Column(db.Integer, nullable=False, default=0)
    questions_wrong = db.Column(db.Integer, nullable=False, default=0)

    # Acurácias
    recent_accuracy = db.Column(db.Float, nullable=True)
    historical_accuracy = db.Column(db.Float, nullable=True)

    # Timestamps
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    last_review_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Consistência
    consecutive_correct = db.Column(db.Integer, nullable=False, default=0)
    consecutive_wrong = db.Column(db.Integer, nullable=False, default=0)

    # Tempo médio de resposta (segundos)
    average_response_time = db.Column(db.Float, nullable=True)

    # Tendência: 'improving', 'stable', 'declining'
    trend = db.Column(db.String(20), nullable=False, default="stable")

    # Relacionamentos
    user = db.relationship("User", backref=db.backref("knowledge_states", lazy=True))
    subject = db.relationship(
        "Subject", backref=db.backref("knowledge_states", lazy=True)
    )
    topic = db.relationship(
        "Topic", backref=db.backref("knowledge_states", lazy=True)
    )

    def __repr__(self):
        return (
            f"<KnowledgeState user={self.user_id} "
            f"topic={self.topic_id} mastery={self.mastery_score}>"
        )

    def to_dict(self) -> dict:
        """Serializa o estado de conhecimento para dicionário."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "subject_id": self.subject_id,
            "topic_id": self.topic_id,
            "mastery_score": self.mastery_score,
            "confidence_score": self.confidence_score,
            "questions_answered": self.questions_answered,
            "questions_correct": self.questions_correct,
            "questions_wrong": self.questions_wrong,
            "recent_accuracy": self.recent_accuracy,
            "historical_accuracy": self.historical_accuracy,
            "last_attempt_at": (
                self.last_attempt_at.isoformat() if self.last_attempt_at else None
            ),
            "last_review_at": (
                self.last_review_at.isoformat() if self.last_review_at else None
            ),
            "consecutive_correct": self.consecutive_correct,
            "consecutive_wrong": self.consecutive_wrong,
            "average_response_time": self.average_response_time,
            "trend": self.trend,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
