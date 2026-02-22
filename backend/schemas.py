from datetime import datetime
from pydantic import BaseModel
from typing import Optional


# --- ETF ---
class ETFUpdate(BaseModel):
    price: Optional[float] = None
    pmc: Optional[float] = None
    qty: Optional[float] = None


class ETFOut(BaseModel):
    id: str
    name: str
    ticker: str
    qty: float
    pmc: float
    price: float
    target_pct: float
    value: float
    gain_eur: float
    gain_pct: float
    weight_pct: float
    delta_pct: float

    class Config:
        from_attributes = True


# --- Cash / Liquidity ---
class CashUpdate(BaseModel):
    amount: Optional[float] = None
    target_pct: Optional[float] = None


class CashOut(BaseModel):
    amount: float
    target_pct: float
    weight_pct: float

    class Config:
        from_attributes = True


class PortfolioOut(BaseModel):
    etfs: list[ETFOut]
    liquidity: CashOut
    total_value: float
    total_invested: float
    total_gain_eur: float
    total_gain_pct: float


# --- Targets ---
class TargetsUpdate(BaseModel):
    targets: dict[str, float]


# --- Rebalance ---
class RebalancePlanItem(BaseModel):
    id: str
    name: str
    invest_eur: float
    shares_to_buy: int
    actual_spend: float
    price_per_share: float
    weight_after_pct: float


class RebalanceOut(BaseModel):
    amount: float
    plan: list[RebalancePlanItem]
    total_spent: float
    leftover: float
    liquidity_after: float


# --- Snapshots ---
class SnapshotCreate(BaseModel):
    date: str
    total_value: float
    total_invested: float = 0


class SnapshotOut(BaseModel):
    id: int
    date: str
    total_value: float
    total_invested: float

    class Config:
        from_attributes = True


# --- Summary ---
class SummaryOut(BaseModel):
    total_value: float
    total_invested: float
    total_gain_eur: float
    total_gain_pct: float
    liquidity: float
    weights: dict[str, float]
    targets: dict[str, float]


# --- Strategie ---

class StrategyCreate(BaseModel):
    """Dati per creare una nuova strategia."""
    name: str
    description: str = ""
    targets: dict[str, float]       # {"world": 70, "em": 15, ..., "cash": 0}


class StrategyUpdate(BaseModel):
    """Campi aggiornabili di una strategia (tutti opzionali)."""
    name: Optional[str] = None
    description: Optional[str] = None
    targets: Optional[dict[str, float]] = None


class StrategyOut(BaseModel):
    """Strategia restituita al frontend."""
    id: int
    name: str
    description: str
    targets: dict[str, float]       # target deserializzati da JSON
    is_active: bool
    created_at: datetime
    activated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StrategyHistoryOut(BaseModel):
    """Singola voce dello storico attivazioni."""
    id: int
    strategy_name: str
    activated_at: datetime

    class Config:
        from_attributes = True
