
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class SportEvent(Base):

    __tablename__ = "sport_events"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True
    )

    sport: Mapped[str] = mapped_column(String(100))
    home_team: Mapped[str] = mapped_column(String(200))
    away_team: Mapped[str] = mapped_column(String(200))

    commence_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )


class ScanRun(Base):

    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="running"
    )

    event_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
