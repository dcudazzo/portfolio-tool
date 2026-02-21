import math
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import ETF, Cash, Snapshot
from schemas import (
    ETFUpdate,
    ETFOut,
    CashUpdate,
    CashOut,
    PortfolioOut,
    TargetsUpdate,
    RebalanceOut,
    RebalancePlanItem,
    SnapshotCreate,
    SnapshotOut,
    SummaryOut,
)

app = FastAPI(title="Portfolio Tracker", version="1.0.0")

# ---------------------------------------------------------------------------
# Startup: create tables & seed data
# ---------------------------------------------------------------------------
SEED_DATA = [
    {
        "id": "world",
        "name": "MSCI AC World",
        "ticker": "Xtrackers MSCI AC World Scr. UCITS ETF 1C",
        "qty": 211,
        "pmc": 40.0320,
        "price": 44.6650,
        "target_pct": 70,
    },
    {
        "id": "em",
        "name": "Emerging Markets",
        "ticker": "Xtrackers MSCI Emerging Markets UCITS ETF 1C",
        "qty": 15,
        "pmc": 64.4460,
        "price": 71.7520,
        "target_pct": 15,
    },
    {
        "id": "gold",
        "name": "Gold ETC",
        "ticker": "Invesco Physical Gold ETC",
        "qty": 2,
        "pmc": 272.0300,
        "price": 409.0900,
        "target_pct": 10,
    },
    {
        "id": "bond13",
        "name": "Bond 1-3Y",
        "ticker": "iShares EUR Govt Bond 1-3yr UCITS ETF EUR (Acc)",
        "qty": 32,
        "pmc": 114.0963,
        "price": 116.4300,
        "target_pct": 5,
    },
    {
        "id": "bond710",
        "name": "Bond 7-10Y",
        "ticker": "Amundi Euro Government Bond 7-10Y UCITS ETF Acc",
        "qty": 17,
        "pmc": 166.2000,
        "price": 172.4300,
        "target_pct": 0,
    },
]


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        if db.query(ETF).count() == 0:
            for item in SEED_DATA:
                db.add(ETF(**item))
            db.commit()
        if db.query(Cash).count() == 0:
            db.add(Cash(id=1, amount=0, target_pct=0))
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_etf_out(etf: ETF, total_value: float) -> ETFOut:
    value = round(etf.price * etf.qty, 2)
    invested = round(etf.pmc * etf.qty, 2)
    gain_eur = round(value - invested, 2)
    gain_pct = round((gain_eur / invested * 100) if invested else 0, 2)
    weight_pct = round((value / total_value * 100) if total_value else 0, 2)
    delta_pct = round(weight_pct - etf.target_pct, 2)
    return ETFOut(
        id=etf.id,
        name=etf.name,
        ticker=etf.ticker,
        qty=etf.qty,
        pmc=etf.pmc,
        price=etf.price,
        target_pct=etf.target_pct,
        value=value,
        gain_eur=gain_eur,
        gain_pct=gain_pct,
        weight_pct=weight_pct,
        delta_pct=delta_pct,
    )


def _get_cash(db: Session) -> Cash:
    cash = db.query(Cash).first()
    if not cash:
        cash = Cash(id=1, amount=0, target_pct=0)
        db.add(cash)
        db.commit()
        db.refresh(cash)
    return cash


def _total_value(db: Session) -> float:
    etfs = db.query(ETF).all()
    cash = _get_cash(db)
    return sum(e.price * e.qty for e in etfs) + cash.amount


def _total_invested(db: Session) -> float:
    etfs = db.query(ETF).all()
    cash = _get_cash(db)
    return sum(e.pmc * e.qty for e in etfs) + cash.amount


# ---------------------------------------------------------------------------
# GET /api/portfolio
# ---------------------------------------------------------------------------
@app.get("/api/portfolio", response_model=PortfolioOut)
def get_portfolio(db: Session = Depends(get_db)):
    etfs = db.query(ETF).all()
    cash = _get_cash(db)
    etf_val = sum(e.price * e.qty for e in etfs)
    total_val = etf_val + cash.amount
    total_inv = sum(e.pmc * e.qty for e in etfs) + cash.amount
    gain_eur = round(total_val - total_inv, 2)
    gain_pct = round((gain_eur / total_inv * 100) if total_inv else 0, 2)

    cash_weight = round((cash.amount / total_val * 100) if total_val else 0, 2)

    return PortfolioOut(
        etfs=[_build_etf_out(e, total_val) for e in etfs],
        liquidity=CashOut(
            amount=cash.amount,
            target_pct=cash.target_pct,
            weight_pct=cash_weight,
        ),
        total_value=round(total_val, 2),
        total_invested=round(total_inv, 2),
        total_gain_eur=gain_eur,
        total_gain_pct=gain_pct,
    )


# ---------------------------------------------------------------------------
# PUT /api/etf/{id}
# ---------------------------------------------------------------------------
@app.put("/api/etf/{etf_id}", response_model=ETFOut)
def update_etf(etf_id: str, data: ETFUpdate, db: Session = Depends(get_db)):
    etf = db.query(ETF).filter(ETF.id == etf_id).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")

    if data.price is not None:
        etf.price = data.price
    if data.pmc is not None:
        etf.pmc = data.pmc
    if data.qty is not None:
        etf.qty = data.qty

    etf.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(etf)

    total_val = _total_value(db)
    return _build_etf_out(etf, total_val)


# ---------------------------------------------------------------------------
# PUT /api/cash
# ---------------------------------------------------------------------------
@app.put("/api/cash", response_model=CashOut)
def update_cash(data: CashUpdate, db: Session = Depends(get_db)):
    cash = _get_cash(db)
    if data.amount is not None:
        cash.amount = data.amount
    if data.target_pct is not None:
        cash.target_pct = data.target_pct
    cash.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cash)

    total_val = _total_value(db)
    cash_weight = round((cash.amount / total_val * 100) if total_val else 0, 2)
    return CashOut(amount=cash.amount, target_pct=cash.target_pct, weight_pct=cash_weight)


# ---------------------------------------------------------------------------
# PUT /api/targets
# ---------------------------------------------------------------------------
@app.put("/api/targets")
def update_targets(data: TargetsUpdate, db: Session = Depends(get_db)):
    total = sum(data.targets.values())
    if abs(total - 100) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"I target devono sommare a 100%. Attuale: {total}%",
        )

    for key, pct in data.targets.items():
        if key == "cash":
            cash = _get_cash(db)
            cash.target_pct = pct
            cash.updated_at = datetime.now(timezone.utc)
        else:
            etf = db.query(ETF).filter(ETF.id == key).first()
            if etf:
                etf.target_pct = pct
                etf.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"status": "ok", "targets": data.targets}


# ---------------------------------------------------------------------------
# GET /api/rebalance?amount=1800
# ---------------------------------------------------------------------------
@app.get("/api/rebalance", response_model=RebalanceOut)
def get_rebalance(amount: float = Query(..., gt=0), db: Session = Depends(get_db)):
    etfs = db.query(ETF).all()
    cash = _get_cash(db)
    etf_total = sum(e.price * e.qty for e in etfs)
    current_total = etf_total + cash.amount
    future_total = current_total + amount

    # Calculate gaps (only for ETFs with target > 0)
    gaps = []
    for e in etfs:
        target_val = future_total * (e.target_pct / 100)
        current_val = e.price * e.qty
        gap = max(0, target_val - current_val)
        gaps.append({"etf": e, "target_val": target_val, "gap": gap})

    total_gap = sum(g["gap"] for g in gaps)

    plan = []
    total_spent = 0

    for g in gaps:
        e = g["etf"]
        if e.target_pct == 0 or g["gap"] <= 0:
            plan.append(
                RebalancePlanItem(
                    id=e.id,
                    name=e.name,
                    invest_eur=0,
                    shares_to_buy=0,
                    actual_spend=0,
                    price_per_share=e.price,
                    weight_after_pct=round(
                        (e.price * e.qty) / future_total * 100, 2
                    ),
                )
            )
            continue

        # Distribute proportionally to gap
        if total_gap > 0:
            invest = (g["gap"] / total_gap) * amount
        else:
            invest = 0

        shares = math.floor(invest / e.price) if e.price > 0 else 0
        actual = round(shares * e.price, 2)
        total_spent += actual

        new_val = e.price * e.qty + actual
        weight_after = round(new_val / future_total * 100, 2)

        plan.append(
            RebalancePlanItem(
                id=e.id,
                name=e.name,
                invest_eur=round(invest, 2),
                shares_to_buy=shares,
                actual_spend=actual,
                price_per_share=e.price,
                weight_after_pct=weight_after,
            )
        )

    leftover = round(amount - total_spent, 2)
    # Cash target allocation for the future total
    cash_target_val = future_total * (cash.target_pct / 100) if cash.target_pct > 0 else 0
    liquidity_after = round(cash.amount + leftover, 2)

    return RebalanceOut(
        amount=amount,
        plan=plan,
        total_spent=round(total_spent, 2),
        leftover=leftover,
        liquidity_after=liquidity_after,
    )


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------
@app.get("/api/snapshots", response_model=list[SnapshotOut])
def get_snapshots(db: Session = Depends(get_db)):
    return db.query(Snapshot).order_by(Snapshot.date).all()


@app.post("/api/snapshots", response_model=SnapshotOut, status_code=201)
def create_snapshot(data: SnapshotCreate, db: Session = Depends(get_db)):
    snap = Snapshot(
        date=data.date,
        total_value=data.total_value,
        total_invested=data.total_invested,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


@app.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    snap = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    db.delete(snap)
    db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/summary
# ---------------------------------------------------------------------------
@app.get("/api/summary", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db)):
    etfs = db.query(ETF).all()
    cash = _get_cash(db)
    etf_val = sum(e.price * e.qty for e in etfs)
    total_val = etf_val + cash.amount
    total_inv = sum(e.pmc * e.qty for e in etfs) + cash.amount
    gain_eur = round(total_val - total_inv, 2)
    gain_pct = round((gain_eur / total_inv * 100) if total_inv else 0, 2)

    weights = {e.id: round((e.price * e.qty) / total_val * 100, 2) if total_val else 0 for e in etfs}
    weights["cash"] = round((cash.amount / total_val * 100) if total_val else 0, 2)
    targets = {e.id: e.target_pct for e in etfs}
    targets["cash"] = cash.target_pct

    return SummaryOut(
        total_value=round(total_val, 2),
        total_invested=round(total_inv, 2),
        total_gain_eur=gain_eur,
        total_gain_pct=gain_pct,
        liquidity=cash.amount,
        weights=weights,
        targets=targets,
    )


# ---------------------------------------------------------------------------
# Serve frontend (must be last, catch-all mount)
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
