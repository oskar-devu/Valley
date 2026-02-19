import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def gen_uuid():
    return str(uuid.uuid4())


class TovConfig(Base):
    """Saved tone-of-voice presets (optional; request can also send inline TOV)."""

    __tablename__ = "tov_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    formality: Mapped[float] = mapped_column(Float, nullable=False)
    warmth: Mapped[float] = mapped_column(Float, nullable=False)
    directness: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
