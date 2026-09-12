"""Catalogo oficial de materias do ENEM."""

from app.extensions import db
from app.models import Subject


ENEM_SUBJECT_CATALOG = (
    ("linguagens", "Português", "#2563EB"),
    ("linguagens", "Literatura", "#7C3AED"),
    ("linguagens", "Inglês", "#0891B2"),
    ("humanas", "História", "#B45309"),
    ("humanas", "Geografia", "#15803D"),
    ("humanas", "Filosofia", "#4F46E5"),
    ("humanas", "Sociologia", "#9333EA"),
    ("natureza", "Biologia", "#16A34A"),
    ("natureza", "Química", "#CA8A04"),
    ("natureza", "Física", "#DC2626"),
    ("matematica", "Matemática", "#1D4ED8"),
    ("redacao", "Redação", "#C2410C"),
)


def provision_subjects(user_id: int) -> list[Subject]:
    """Garante que o usuario possua todas as materias oficiais."""
    existing = {
        subject.nome: subject
        for subject in Subject.query.filter_by(user_id=user_id).all()
    }

    for area, name, color in ENEM_SUBJECT_CATALOG:
        if name not in existing:
            subject = Subject(
                nome=name,
                cor=color,
                area=area,
                user_id=user_id,
            )
            db.session.add(subject)
            existing[name] = subject

    db.session.flush()
    return [existing[name] for _, name, _ in ENEM_SUBJECT_CATALOG]
