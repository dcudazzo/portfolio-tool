from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from database import Base


class ETF(Base):
    __tablename__ = "etfs"

    id = Column(String, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    ticker = Column(Text, nullable=False)
    qty = Column(Float, nullable=False, default=0)
    pmc = Column(Float, nullable=False, default=0)
    price = Column(Float, nullable=False, default=0)
    target_pct = Column(Float, nullable=False, default=0)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False)
    total_value = Column(Float, nullable=False)
    total_invested = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
