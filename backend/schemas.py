from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


# --- Asset (ex ETF) ---
class AssetCreate(BaseModel):
    id: str
    name: str
    ticker: str
    yahoo_ticker: Optional[str] = None
    isin: Optional[str] = None
    type: str = "etf"
    qty: float = 0
    pmc: float = 0
    price: float = 0
    target_pct: float = 0


class AssetUpdate(BaseModel):
    price: Optional[float] = None
    pmc: Optional[float] = None
    qty: Optional[float] = None
    yahoo_ticker: Optional[str] = None
    isin: Optional[str] = None
    type: Optional[str] = None


class AssetOut(BaseModel):
    id: str
    name: str
    ticker: str
    yahoo_ticker: Optional[str] = None
    isin: Optional[str] = None
    type: str
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
    etfs: list[AssetOut]
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


class RebalanceLogCreate(BaseModel):
    amount: float = Field(gt=0)
    total_spent: float = Field(ge=0)
    plan: list[RebalancePlanItem]


class RebalanceLogOut(BaseModel):
    id: int
    executed_at: datetime
    amount: float
    total_spent: float
    plan: list[RebalancePlanItem]

    class Config:
        from_attributes = True


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


# --- Price update (Yahoo Finance) ---

class PriceUpdateResult(BaseModel):
    id: str
    name: str
    old_price: float
    new_price: float
    status: str             # "ok", "skipped", "error"
    error: Optional[str] = None


class PriceUpdateOut(BaseModel):
    updated: int
    skipped: int
    errors: int
    results: list[PriceUpdateResult]


# --- Ticker search (Yahoo Finance) ---

class TickerSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str
    type: str           # "ETF", "Equity", "Cryptocurrency", ...
    currency: str = ""
