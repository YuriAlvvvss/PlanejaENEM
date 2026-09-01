"""
Modelos de persistência do AI Gateway - PlanejaENEM 5.0.

Modelo AIUsage para registro de chamadas à IA generativa.
Persiste métricas de uso: tokens, latência, custo estimado, status.

REGRA DE OURO: NUNCA armazena API key, senha, token, sessão,
prompt completo com dados sensíveis ou dados pessoais desnecessários.
"""

from datetime import datetime, timezone

from app.extensions import db


class AIUsage(db.Model):
    """Registro de uso de IA generativa."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        db.Index("idx_ai_usage_user_feature_created", "user_id", "feature", "created_at"),
        db.Index("idx_ai_usage_feature_created", "feature", "created_at"),
        db.Index("idx_ai_usage_created_at", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    feature = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    prompt_version = db.Column(db.String(20), nullable=False, default="1.0")
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    latency_ms = db.Column(db.Float, nullable=False, default=0.0)
    estimated_cost = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default="success")
    error_type = db.Column(db.String(50), nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", backref=db.backref("ai_usage", lazy=True))

    def __repr__(self) -> str:
        return (
            f"<AIUsage feature={self.feature} model={self.model} "
            f"tokens={self.total_tokens} status={self.status}>"
        )

    def to_dict(self) -> dict:
        """Serializa para dict (sem dados sensíveis)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "feature": self.feature,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "estimated_cost": self.estimated_cost,
            "status": self.status,
            "error_type": self.error_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
