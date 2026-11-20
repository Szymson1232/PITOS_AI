
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    Float,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class SportEvent(Base):
    __tablename__ = "sport_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sport: Mapped[str] = mapped_column(String(100))
    home_team: Mapped[str] = mapped_column(String(200))
    away_team: Mapped[str] = mapped_column(String(200))
    commence_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[str] = mapped_column(String(30), default="running")
    event_count: Mapped[int] = mapped_column(Integer, default=0)


class TipRecord(Base):
    __tablename__ = "tip_records"

    __table_args__ = (
        UniqueConstraint("record_key", name="uq_tip_record_key"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    record_key: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)

    event_id: Mapped[str] = mapped_column(String(100), default="")
    sport: Mapped[str] = mapped_column(String(100), default="")
    home_team: Mapped[str] = mapped_column(String(200), default="")
    away_team: Mapped[str] = mapped_column(String(200), default="")
    selection: Mapped[str] = mapped_column(String(300), nullable=False)

    odds: Mapped[float] = mapped_column(Float, nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    ev: Mapped[float] = mapped_column(Float, default=0.0)

    stake_units: Mapped[int] = mapped_column(Integer, default=1)
    stake_amount: Mapped[float] = mapped_column(Float, default=25.0)

    status: Mapped[str] = mapped_column(String(30), default="pending")
    result: Mapped[str] = mapped_column(String(30), default="pending")
    profit: Mapped[float] = mapped_column(Float, default=0.0)

    details: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
