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
