from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean
from database import Base


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    ticker = Column(Text, nullable=False)
    yahoo_ticker = Column(Text, nullable=True)
    isin = Column(Text, nullable=True)
    type = Column(Text, nullable=False, default="etf")
    qty = Column(Float, nullable=False, default=0)
    pmc = Column(Float, nullable=False, default=0)
    price = Column(Float, nullable=False, default=0)
    target_pct = Column(Float, nullable=False, default=0)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Cash(Base):
    __tablename__ = "cash"

    id = Column(Integer, primary_key=True, default=1)
    amount = Column(Float, nullable=False, default=0)
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


# ---------- Strategie di allocazione ----------

class Strategy(Base):
    """Template di allocazione target salvato dall'utente.
    Una sola strategia puo' essere attiva alla volta (is_active=True).
    I target sono memorizzati come stringa JSON: {"world": 70, "em": 15, ...}
    """
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=False, default="")
    targets_json = Column(Text, nullable=False)       # JSON dei target %
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime, nullable=True)     # ultima attivazione


class StrategyHistory(Base):
    """Log delle attivazioni di strategia nel tempo.
    Salva il nome (non FK) cosi' il record resta anche se la strategia viene cancellata.
    """
    __tablename__ = "strategy_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(Text, nullable=False)
    activated_at = Column(DateTime, nullable=False,
                          default=lambda: datetime.now(timezone.utc))
