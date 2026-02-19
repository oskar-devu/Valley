import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def gen_uuid():
    return str(uuid.uuid4())


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    linkedin_url: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    profile_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    sequences = relationship("MessageSequence", back_populates="prospect")
