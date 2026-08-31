"""
Tipos de dados do Decision Engine - PlanejaENEM 4.0.

Define enums, dataclasses e tipos utilizados pelo motor de decisão.
Todas as decisões são determinísticas e não utilizam IA generativa.
"""

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Optional


class StudyAction(Enum):
    """Ações de estudo recomendadas pelo sistema."""
    LEARN = "learn"
    PRACTICE = "practice"
    ENEM_QUESTIONS = "enem_questions"
    REVIEW = "review"
    DIFFICULT_QUESTIONS = "difficult_questions"
    MOCK_EXAM = "mock_exam"


class SessionStatus(Enum):
    """Status possíveis de uma sessão de estudo."""
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    MISSED = "missed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class ReasonCode(Enum):
    """
    Códigos de motivo para recomendações.
    
    Cada recomendação possui uma lista de reason_codes que explicam
    por que aquele assunto/ação foi recomendado.
    """
    LOW_MASTERY = "low_mastery"
    MODERATE_MASTERY = "moderate_mastery"
    RECENT_ACCURACY_DROP = "recent_accuracy_drop"
    RECENT_POOR_PERFORMANCE = "recent_poor_performance"
    PERFORMANCE_DECLINING = "performance_declining"
    OVERDUE_REVIEW = "overdue_review"
    EXAM_URGENCY = "exam_urgency"
    HIGH_DIFFICULTY = "high_difficulty"
    LOW_CONFIDENCE = "low_confidence"
    STRONG_PERFORMANCE = "strong_performance"
    BALANCE_AREA = "balance_area"
    MISSED_SESSION = "missed_session"
    NO_DATA = "no_data"
    NEEDS_INITIAL_ASSESSMENT = "needs_initial_assessment"
    TIME_CONSTRAINT = "time_constraint"
    WEEKLY_GOAL_EXCEEDED = "weekly_goal_exceeded"
    CONSECUTIVE_LIMIT = "consecutive_limit"


class MasteryLevel(Enum):
    """
    Níveis de domínio do aluno.
    
    - CRITICAL: 0-39 (precisa de teoria urgente)
    - LOW: 40-59 (precisa de exercícios)
    - MEDIUM: 60-74 (pode praticar questões)
    - GOOD: 75-89 (questões ENEM + revisão)
    - EXCELLENT: 90-100 (questões difíceis + manutenção)
    """
    CRITICAL = "critical"
    LOW = "low"
    MEDIUM = "medium"
    GOOD = "good"
    EXCELLENT = "excellent"


class StudyPhase(Enum):
    """Fases de estudo baseadas na proximidade do ENEM."""
    LONG_TERM = "long_term"
    MEDIUM_TERM = "medium_term"
    FINAL_STRETCH = "final_stretch"


class ConflictType(Enum):
    """Tipos de conflitos que o sistema pode detectar."""
    WEEKLY_GOAL_IMPOSSIBLE = "weekly_goal_impossible"
    EXCESS_SESSIONS = "excess_sessions"
    OVERDUE_REVIEW_CONFLICT = "overdue_review_conflict"
    TIME_SLOT_CONFLICT = "time_slot_conflict"
    NO_AVAILABILITY = "no_availability"
    DAILY_LIMIT_EXCEEDED = "daily_limit_exceeded"
    SUBJECT_IMBALANCE = "subject_imbalance"


class ConflictSeverity(Enum):
    """Severidade dos conflitos."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class StudyRecommendation:
    """
    Recomendação de estudo gerada pelo Decision Engine.
    
    Representa uma ação específica que o aluno deve realizar,
    com todas as informações necessárias para execução.
    """
    priority: int
    subject_id: int
    topic_id: Optional[int]
    action: StudyAction
    duration_minutes: int
    recommended_date: date
    score: float
    mastery_score: float
    confidence_score: float
    reason_codes: list[ReasonCode]
    explanation: str
    study_phase: StudyPhase
    area: str = "outro"
    subject_name: str = ""
    topic_name: str = ""
    
    def to_dict(self) -> dict:
        """Converte para dicionário serializável."""
        return {
            "priority": self.priority,
            "subject_id": self.subject_id,
            "topic_id": self.topic_id,
            "action": self.action.value,
            "duration_minutes": self.duration_minutes,
            "recommended_date": self.recommended_date.isoformat(),
            "score": self.score,
            "mastery_score": self.mastery_score,
            "confidence_score": self.confidence_score,
            "reason_codes": [rc.value for rc in self.reason_codes],
            "explanation": self.explanation,
            "study_phase": self.study_phase.value,
            "area": self.area,
            "subject_name": self.subject_name,
            "topic_name": self.topic_name,
        }


@dataclass
class StudySlot:
    """Slot de tempo disponível para estudo."""
    date: date
    start_time: time
    end_time: time
    duration_minutes: int


@dataclass
class WeeklyAvailability:
    """
    Disponibilidade semanal do aluno.
    
    Define as restrições de tempo que o Decision Engine deve respeitar.
    """
    days: list[str]
    hours: list[str]
    daily_minutes: int
    weekly_goal_minutes: int
    max_session_minutes: int = 120


@dataclass
class TopicContext:
    """
    Contexto completo de um tópico para avaliação.
    
    Inclui dados de domínio, desempenho, revisão e histórico.
    """
    topic_id: int
    subject_id: int
    topic_name: str
    subject_name: str
    area: str
    mastery_score: float
    confidence_score: float
    recent_accuracy: Optional[float]
    historical_accuracy: Optional[float]
    questions_answered: int
    questions_correct: int
    questions_wrong: int
    consecutive_correct: int
    consecutive_wrong: int
    last_attempt_at: Optional[date]
    last_review_at: Optional[date]
    subject_difficulty: int
    subject_priority: int
    days_until_exam: int
    overdue_reviews: int = 0
    missed_sessions: int = 0
    
    @property
    def mastery_level(self) -> MasteryLevel:
        """Retorna o nível de domínio baseado no score."""
        if self.mastery_score >= 90:
            return MasteryLevel.EXCELLENT
        elif self.mastery_score >= 75:
            return MasteryLevel.GOOD
        elif self.mastery_score >= 60:
            return MasteryLevel.MEDIUM
        elif self.mastery_score >= 40:
            return MasteryLevel.LOW
        else:
            return MasteryLevel.CRITICAL


@dataclass
class RankingResult:
    """Resultado do cálculo de ranking para um tópico."""
    final_score: float
    components: dict
    weights: dict
    reason_codes: list[ReasonCode]
    recommended_action: StudyAction
    recommended_duration: int


@dataclass
class Conflict:
    """Conflito detectado pelo sistema."""
    conflict_type: ConflictType
    severity: ConflictSeverity
    details: str
    affected_subjects: list[int] = field(default_factory=list)
    affected_dates: list[date] = field(default_factory=list)


@dataclass
class PlanSimulation:
    """Resultado de simulação de um plano de estudo."""
    plan_name: str
    total_minutes: int
    total_sessions: int
    coverage_score: float
    priority_coverage: dict
    recommendations: list[StudyRecommendation]


@dataclass
class RecommendationHistory:
    """Registro histórico de uma recomendação."""
    id: int
    user_id: int
    subject_id: int
    topic_id: Optional[int]
    action: StudyAction
    recommended_date: date
    score: float
    reason_codes: list[ReasonCode]
    result: Optional[str] = None
    created_at: Optional[date] = None
