import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def gen_uuid():
    return str(uuid.uuid4())


class AIGeneration(Base):
    __tablename__ = "ai_generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    sequence_id: Mapped[str] = mapped_column(String(36), ForeignKey("message_sequences.id", ondelete="CASCADE"), nullable=False)
    model_used: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    sequence = relationship("MessageSequence", back_populates="ai_generations")
