import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def gen_uuid():
    return str(uuid.uuid4())


class MessageSequence(Base):
    __tablename__ = "message_sequences"
    __table_args__ = (Index("ix_message_sequences_prospect_created", "prospect_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    prospect_id: Mapped[str] = mapped_column(String(36), ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    tov_config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # snapshot: formality, warmth, directness
    company_context: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_length: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    prospect = relationship("Prospect", back_populates="sequences")
    messages = relationship("SequenceMessage", back_populates="sequence", order_by="SequenceMessage.step_number")
    ai_generations = relationship("AIGeneration", back_populates="sequence")


class SequenceMessage(Base):
    __tablename__ = "sequence_messages"
    __table_args__ = (UniqueConstraint("sequence_id", "step_number", name="uq_sequence_message_step"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    sequence_id: Mapped[str] = mapped_column(String(36), ForeignKey("message_sequences.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking_process: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    sequence = relationship("MessageSequence", back_populates="messages")
