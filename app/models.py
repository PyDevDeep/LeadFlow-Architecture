from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class LEEDData(Base):
    """Модель для зберігання LEED даних"""

    __tablename__ = "leed_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(500), unique=True, index=True)
    status = Column(
        String(50), default="pending"
    )  # pending, processing, completed, failed
    is_sent: Mapped[bool] = mapped_column(default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<LEEDData(id={self.id}, title={self.title})>"
