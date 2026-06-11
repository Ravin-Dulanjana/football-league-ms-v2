import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ClubStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    short_name: Mapped[str | None] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(32), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    # Stores the S3 object key (e.g. "clubs/logos/uuid.jpg"), not a URL.
    # The CloudFront URL is built at read time by get_file_url() in storage.py.
    logo_key: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[ClubStatus] = mapped_column(
        Enum(
            ClubStatus,
            name="clubstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ClubStatus.ACTIVE,
    )
    established_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    president_name: Mapped[str | None] = mapped_column(String(128))
    secretary_name: Mapped[str | None] = mapped_column(String(128))
    treasurer_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
