import json
import math
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import Asset, Cash, Snapshot, Strategy, StrategyHistory, RebalanceLog
from schemas import (
    AssetCreate,
    AssetUpdate,
    AssetOut,
    CashUpdate,
    CashOut,
    PortfolioOut,
    TargetsUpdate,
    RebalanceOut,
    RebalancePlanItem,
    RebalanceLogCreate,
    RebalanceLogOut,
    SnapshotCreate,
    SnapshotOut,
    SummaryOut,
    StrategyCreate,
    StrategyUpdate,
    StrategyOut,
    StrategyHistoryOut,
    PriceUpdateResult,
    PriceUpdateOut,
    TickerSearchResult,
)

app = FastAPI(title="Portfolio Tracker", version="1.4.0")
_scheduler = BackgroundScheduler()

# ---------------------------------------------------------------------------
# Tipi di asset ammessi
# ---------------------------------------------------------------------------
ASSET_TYPES = {"etf", "etc", "azione", "crypto", "obbligazione"}

# ---------------------------------------------------------------------------
# Startup: migrate, create tables & seed data
# ---------------------------------------------------------------------------
SEED_DATA = [
    {
        "id": "world",
        "name": "MSCI AC World",
        "ticker": "Xtrackers MSCI AC World Scr. UCITS ETF 1C",
        "type": "etf",
        "qty": 211,
        "pmc": 40.0320,
        "price": 44.6650,
        "target_pct": 70,
    },
    {
        "id": "em",
        "name": "Emerging Markets",
        "ticker": "Xtrackers MSCI Emerging Markets UCITS ETF 1C",
        "type": "etf",
        "qty": 15,
        "pmc": 64.4460,
        "price": 71.7520,
        "target_pct": 15,
    },
    {
        "id": "gold",
        "name": "Gold ETC",
        "ticker": "Invesco Physical Gold ETC",
        "type": "etc",
        "qty": 2,
        "pmc": 272.0300,
        "price": 409.0900,
        "target_pct": 10,
    },
    {
        "id": "bond13",
        "name": "Bond 1-3Y",
        "ticker": "iShares EUR Govt Bond 1-3yr UCITS ETF EUR (Acc)",
        "type": "etf",
        "qty": 32,
        "pmc": 114.0963,
        "price": 116.4300,
        "target_pct": 5,
    },
    {
        "id": "bond710",
        "name": "Bond 7-10Y",
        "ticker": "Amundi Euro Government Bond 7-10Y UCITS ETF Acc",
        "type": "etf",
        "qty": 17,
        "pmc": 166.2000,
        "price": 172.4300,
        "target_pct": 0,
    },
]


def _migrate_etfs_to_assets():
    """Migra la tabella 'etfs' in 'assets' se necessario (aggiunta v1.3)."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "etfs" in tables and "assets" not in tables:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE etfs RENAME TO assets"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN type TEXT DEFAULT 'etf'"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN isin TEXT"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN yahoo_ticker TEXT"))
            conn.execute(text("UPDATE assets SET type = 'etc' WHERE id = 'gold'"))


@app.on_event("startup")
def startup():
    """Crea le tabelle, inserisce i dati iniziali e avvia lo scheduler."""
    # Migrazione etfs → assets (prima di create_all)
    _migrate_etfs_to_assets()

    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        # Seed Asset
        if db.query(Asset).count() == 0:
            for item in SEED_DATA:
                db.add(Asset(**item))
            db.commit()

        # Seed Cash
        if db.query(Cash).count() == 0:
            db.add(Cash(id=1, amount=0, target_pct=0))
            db.commit()

        # Seed strategia predefinita (solo se non ne esiste nessuna)
        if db.query(Strategy).count() == 0:
            seed_targets = {s["id"]: s["target_pct"] for s in SEED_DATA}
            seed_targets["cash"] = 0
            now = datetime.now(timezone.utc)
            db.add(Strategy(
                name="Predefinita",
                description="Allocazione iniziale del portafoglio",
                targets_json=json.dumps(seed_targets),
                is_active=True,
                activated_at=now,
            ))
            db.add(StrategyHistory(
                strategy_name="Predefinita",
                activated_at=now,
            ))
            db.commit()

        # Template pronti all'uso: aggiunge solo quelli che non esistono gia'
        STRATEGY_TEMPLATES = [
            ("Aggressiva 20Y", "Orizzonte lungo, forte azionario",
             {"world": 75, "em": 15, "gold": 5, "bond13": 0, "bond710": 0, "cash": 5}),
            ("Moderata 10Y", "Bilanciata, orizzonte medio",
             {"world": 50, "em": 10, "gold": 10, "bond13": 15, "bond710": 5, "cash": 10}),
            ("Pre-pensione", "Conservativa, alta liquidita e bond",
             {"world": 30, "em": 5, "gold": 10, "bond13": 25, "bond710": 10, "cash": 20}),
        ]
        for name, desc, targets in STRATEGY_TEMPLATES:
            if not db.query(Strategy).filter(Strategy.name == name).first():
                db.add(Strategy(
                    name=name, description=desc,
                    targets_json=json.dumps(targets),
                ))
        db.commit()
    finally:
        db.close()

    # Avvia lo scheduler per l'aggiornamento prezzi automatico
    def _scheduled_price_update():
        db = next(get_db())
        try:
            _do_price_update(db)
        except Exception as exc:
            print(f"[scheduler] Errore auto-update prezzi: {exc}")
        finally:
            db.close()

    _scheduler.add_job(_scheduled_price_update, "cron", hour=9, minute=0)
    _scheduler.start()
    print("[scheduler] Avviato — auto-update prezzi ogni giorno alle 09:00")


@app.on_event("shutdown")
def shutdown():
    _scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_asset_out(asset: Asset, total_value: float) -> AssetOut:
    value = round(asset.price * asset.qty, 2)
    invested = round(asset.pmc * asset.qty, 2)
    gain_eur = round(value - invested, 2)
    gain_pct = round((gain_eur / invested * 100) if invested else 0, 2)
    weight_pct = round((value / total_value * 100) if total_value else 0, 2)
    delta_pct = round(weight_pct - asset.target_pct, 2)
    return AssetOut(
        id=asset.id,
        name=asset.name,
        ticker=asset.ticker,
        yahoo_ticker=asset.yahoo_ticker,
        isin=asset.isin,
        type=asset.type or "etf",
        qty=asset.qty,
        pmc=asset.pmc,
        price=asset.price,
        target_pct=asset.target_pct,
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
    assets = db.query(Asset).all()
    cash = _get_cash(db)
    return sum(a.price * a.qty for a in assets) + cash.amount


def _total_invested(db: Session) -> float:
    assets = db.query(Asset).all()
    cash = _get_cash(db)
    return sum(a.pmc * a.qty for a in assets) + cash.amount


# ---------------------------------------------------------------------------
# GET /api/portfolio
# ---------------------------------------------------------------------------
@app.get("/api/portfolio", response_model=PortfolioOut)
def get_portfolio(db: Session = Depends(get_db)):
    assets = db.query(Asset).all()
    cash = _get_cash(db)
    asset_val = sum(a.price * a.qty for a in assets)
    total_val = asset_val + cash.amount
    total_inv = sum(a.pmc * a.qty for a in assets) + cash.amount
    gain_eur = round(total_val - total_inv, 2)
    gain_pct = round((gain_eur / total_inv * 100) if total_inv else 0, 2)

    cash_weight = round((cash.amount / total_val * 100) if total_val else 0, 2)

    return PortfolioOut(
        etfs=[_build_asset_out(a, total_val) for a in assets],
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
# POST /api/assets — Aggiunge un nuovo strumento
# ---------------------------------------------------------------------------
@app.post("/api/assets", response_model=AssetOut, status_code=201)
def create_asset(data: AssetCreate, db: Session = Depends(get_db)):
    if data.type not in ASSET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo non valido. Ammessi: {', '.join(sorted(ASSET_TYPES))}",
        )
    if db.query(Asset).filter(Asset.id == data.id).first():
        raise HTTPException(status_code=400, detail=f"Esiste gia' un asset con id '{data.id}'")

    asset = Asset(
        id=data.id,
        name=data.name,
        ticker=data.ticker,
        yahoo_ticker=data.yahoo_ticker,
        isin=data.isin,
        type=data.type,
        qty=data.qty,
        pmc=data.pmc,
        price=data.price,
        target_pct=data.target_pct,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    total_val = _total_value(db)
    return _build_asset_out(asset, total_val)


# ---------------------------------------------------------------------------
# PUT /api/assets/{id}
# ---------------------------------------------------------------------------
@app.put("/api/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: str, data: AssetUpdate, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if data.price is not None:
        asset.price = data.price
    if data.pmc is not None:
        asset.pmc = data.pmc
    if data.qty is not None:
        asset.qty = data.qty
    if data.yahoo_ticker is not None:
        asset.yahoo_ticker = data.yahoo_ticker
    if data.isin is not None:
        asset.isin = data.isin
    if data.type is not None:
        if data.type not in ASSET_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo non valido. Ammessi: {', '.join(sorted(ASSET_TYPES))}",
            )
        asset.type = data.type

    asset.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(asset)

    total_val = _total_value(db)
    return _build_asset_out(asset, total_val)


# ---------------------------------------------------------------------------
# DELETE /api/assets/{id}
# ---------------------------------------------------------------------------
@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Protezione: non eliminare l'ultimo asset
    if db.query(Asset).count() <= 1:
        raise HTTPException(status_code=400, detail="Non puoi eliminare l'ultimo asset")

    # Pulisci la chiave dalle strategie
    for strategy in db.query(Strategy).all():
        targets = json.loads(strategy.targets_json)
        if asset_id in targets:
            del targets[asset_id]
            strategy.targets_json = json.dumps(targets)

    db.delete(asset)
    db.commit()
    return {"status": "ok"}


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
    """Aggiorna i target sugli Asset/Cash e sincronizza la strategia attiva."""
    total = sum(data.targets.values())
    if abs(total - 100) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"I target devono sommare a 100%. Attuale: {total}%",
        )

    # Aggiorna i target sui singoli Asset e Cash
    for key, pct in data.targets.items():
        if key == "cash":
            cash = _get_cash(db)
            cash.target_pct = pct
            cash.updated_at = datetime.now(timezone.utc)
        else:
            asset = db.query(Asset).filter(Asset.id == key).first()
            if asset:
                asset.target_pct = pct
                asset.updated_at = datetime.now(timezone.utc)

    # Sincronizza con la strategia attiva (se esiste)
    active = db.query(Strategy).filter(Strategy.is_active == True).first()
    if active:
        active.targets_json = json.dumps(data.targets)

    db.commit()
    return {"status": "ok", "targets": data.targets}


# ---------------------------------------------------------------------------
# GET /api/rebalance?amount=1800
# ---------------------------------------------------------------------------
@app.get("/api/rebalance", response_model=RebalanceOut)
def get_rebalance(amount: float = Query(..., gt=0), db: Session = Depends(get_db)):
    assets = db.query(Asset).all()
    cash = _get_cash(db)
    asset_total = sum(a.price * a.qty for a in assets)
    current_total = asset_total + cash.amount
    future_total = current_total + amount

    # Calculate gaps (only for assets with target > 0)
    gaps = []
    for a in assets:
        target_val = future_total * (a.target_pct / 100)
        current_val = a.price * a.qty
        gap = max(0, target_val - current_val)
        gaps.append({"asset": a, "target_val": target_val, "gap": gap})

    total_gap = sum(g["gap"] for g in gaps)

    plan = []
    total_spent = 0

    for g in gaps:
        a = g["asset"]
        if a.target_pct == 0 or g["gap"] <= 0:
            plan.append(
                RebalancePlanItem(
                    id=a.id,
                    name=a.name,
                    invest_eur=0,
                    shares_to_buy=0,
                    actual_spend=0,
                    price_per_share=a.price,
                    weight_after_pct=round(
                        (a.price * a.qty) / future_total * 100, 2
                    ),
                )
            )
            continue

        # Distribute proportionally to gap
        if total_gap > 0:
            invest = (g["gap"] / total_gap) * amount
        else:
            invest = 0

        shares = math.floor(invest / a.price) if a.price > 0 else 0
        actual = round(shares * a.price, 2)
        total_spent += actual

        new_val = a.price * a.qty + actual
        weight_after = round(new_val / future_total * 100, 2)

        plan.append(
            RebalancePlanItem(
                id=a.id,
                name=a.name,
                invest_eur=round(invest, 2),
                shares_to_buy=shares,
                actual_spend=actual,
                price_per_share=a.price,
                weight_after_pct=weight_after,
            )
        )

    leftover = round(amount - total_spent, 2)
    liquidity_after = round(cash.amount + leftover, 2)

    return RebalanceOut(
        amount=amount,
        plan=plan,
        total_spent=round(total_spent, 2),
        leftover=leftover,
        liquidity_after=liquidity_after,
    )


# ---------------------------------------------------------------------------
# Helpers strategie
# ---------------------------------------------------------------------------

def _strategy_to_out(s: Strategy) -> StrategyOut:
    """Converte un record Strategy nel suo schema di output, deserializzando il JSON."""
    return StrategyOut(
        id=s.id,
        name=s.name,
        description=s.description,
        targets=json.loads(s.targets_json),
        is_active=s.is_active,
        created_at=s.created_at,
        activated_at=s.activated_at,
    )


def _apply_strategy_targets(db: Session, targets: dict):
    """Copia i target di una strategia sugli Asset e Cash (li rende attivi)."""
    for key, pct in targets.items():
        if key == "cash":
            cash = _get_cash(db)
            cash.target_pct = pct
            cash.updated_at = datetime.now(timezone.utc)
        else:
            asset = db.query(Asset).filter(Asset.id == key).first()
            if asset:
                asset.target_pct = pct
                asset.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# GET /api/strategies
# ---------------------------------------------------------------------------
@app.get("/api/strategies", response_model=list[StrategyOut])
def list_strategies(db: Session = Depends(get_db)):
    """Restituisce tutte le strategie, ordinate per nome."""
    rows = db.query(Strategy).order_by(Strategy.name).all()
    return [_strategy_to_out(s) for s in rows]


# ---------------------------------------------------------------------------
# POST /api/strategies
# ---------------------------------------------------------------------------
@app.post("/api/strategies", response_model=StrategyOut, status_code=201)
def create_strategy(data: StrategyCreate, db: Session = Depends(get_db)):
    """Crea una nuova strategia. I target devono sommare a 100%."""
    total = sum(data.targets.values())
    if abs(total - 100) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"I target devono sommare a 100%. Attuale: {total}%",
        )

    # Controlla nome univoco
    if db.query(Strategy).filter(Strategy.name == data.name).first():
        raise HTTPException(status_code=400, detail="Esiste gia' una strategia con questo nome")

    s = Strategy(
        name=data.name,
        description=data.description,
        targets_json=json.dumps(data.targets),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _strategy_to_out(s)


# ---------------------------------------------------------------------------
# PUT /api/strategies/{id}
# ---------------------------------------------------------------------------
@app.put("/api/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, data: StrategyUpdate, db: Session = Depends(get_db)):
    """Modifica nome, descrizione o target di una strategia esistente."""
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategia non trovata")

    if data.name is not None:
        # Controlla che il nuovo nome non sia gia' usato da un'altra strategia
        existing = db.query(Strategy).filter(Strategy.name == data.name, Strategy.id != strategy_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Esiste gia' una strategia con questo nome")
        s.name = data.name

    if data.description is not None:
        s.description = data.description

    if data.targets is not None:
        total = sum(data.targets.values())
        if abs(total - 100) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"I target devono sommare a 100%. Attuale: {total}%",
            )
        s.targets_json = json.dumps(data.targets)
        # Se e' la strategia attiva, aggiorna anche Asset/Cash
        if s.is_active:
            _apply_strategy_targets(db, data.targets)

    db.commit()
    db.refresh(s)
    return _strategy_to_out(s)


# ---------------------------------------------------------------------------
# DELETE /api/strategies/{id}
# ---------------------------------------------------------------------------
@app.delete("/api/strategies/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Elimina una strategia. Non si puo' eliminare quella attiva."""
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategia non trovata")
    if s.is_active:
        raise HTTPException(status_code=400, detail="Non puoi eliminare la strategia attiva")
    db.delete(s)
    db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/strategies/{id}/activate
# ---------------------------------------------------------------------------
@app.post("/api/strategies/{strategy_id}/activate", response_model=StrategyOut)
def activate_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Attiva una strategia: copia i suoi target sugli Asset/Cash e logga l'attivazione."""
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategia non trovata")

    now = datetime.now(timezone.utc)

    # Disattiva tutte le strategie
    db.query(Strategy).update({Strategy.is_active: False})

    # Attiva quella selezionata
    s.is_active = True
    s.activated_at = now

    # Copia i target della strategia sugli Asset e Cash
    targets = json.loads(s.targets_json)
    _apply_strategy_targets(db, targets)

    # Registra nello storico
    db.add(StrategyHistory(strategy_name=s.name, activated_at=now))

    db.commit()
    db.refresh(s)
    return _strategy_to_out(s)


# ---------------------------------------------------------------------------
# GET /api/strategies/history
# ---------------------------------------------------------------------------
@app.get("/api/strategies/history", response_model=list[StrategyHistoryOut])
def get_strategy_history(db: Session = Depends(get_db)):
    """Restituisce lo storico delle attivazioni (piu' recenti prima)."""
    return (
        db.query(StrategyHistory)
        .order_by(StrategyHistory.activated_at.desc())
        .limit(50)
        .all()
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
    assets = db.query(Asset).all()
    cash = _get_cash(db)
    asset_val = sum(a.price * a.qty for a in assets)
    total_val = asset_val + cash.amount
    total_inv = sum(a.pmc * a.qty for a in assets) + cash.amount
    gain_eur = round(total_val - total_inv, 2)
    gain_pct = round((gain_eur / total_inv * 100) if total_inv else 0, 2)

    weights = {a.id: round((a.price * a.qty) / total_val * 100, 2) if total_val else 0 for a in assets}
    weights["cash"] = round((cash.amount / total_val * 100) if total_val else 0, 2)
    targets = {a.id: a.target_pct for a in assets}
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
# POST /api/prices/update — Aggiorna prezzi via Yahoo Finance
# ---------------------------------------------------------------------------
def _do_price_update(db: Session) -> PriceUpdateOut:
    """Aggiorna i prezzi di tutti gli asset con yahoo_ticker. Usato dall'endpoint e dallo scheduler."""
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("yfinance non installato. Esegui: pip install yfinance")

    assets = db.query(Asset).all()
    results = []
    updated = 0
    skipped = 0
    errors = 0

    # Ottieni tasso EUR/USD per conversioni
    eur_usd_rate = None

    for asset in assets:
        if not asset.yahoo_ticker:
            results.append(PriceUpdateResult(
                id=asset.id, name=asset.name,
                old_price=asset.price, new_price=asset.price,
                status="skipped",
            ))
            skipped += 1
            continue

        try:
            ticker = yf.Ticker(asset.yahoo_ticker)
            info = ticker.fast_info
            new_price = info.get("lastPrice") or info.get("last_price")
            currency = info.get("currency", "EUR")

            if new_price is None:
                raise ValueError("Prezzo non disponibile")

            # Converti in EUR se necessario
            if currency and currency.upper() != "EUR":
                if eur_usd_rate is None and currency.upper() == "USD":
                    try:
                        fx = yf.Ticker("EURUSD=X")
                        eur_usd_rate = fx.fast_info.get("lastPrice") or fx.fast_info.get("last_price") or 1.0
                    except Exception:
                        eur_usd_rate = 1.0

                if currency.upper() == "USD" and eur_usd_rate:
                    new_price = new_price / eur_usd_rate
                elif currency.upper() == "GBP":
                    try:
                        fx = yf.Ticker("EURGBP=X")
                        rate = fx.fast_info.get("lastPrice") or fx.fast_info.get("last_price") or 1.0
                        new_price = new_price / rate
                    except Exception:
                        pass

            new_price = round(new_price, 4)
            old_price = asset.price
            asset.price = new_price
            asset.updated_at = datetime.now(timezone.utc)

            results.append(PriceUpdateResult(
                id=asset.id, name=asset.name,
                old_price=old_price, new_price=new_price,
                status="ok",
            ))
            updated += 1

        except Exception as exc:
            results.append(PriceUpdateResult(
                id=asset.id, name=asset.name,
                old_price=asset.price, new_price=asset.price,
                status="error", error=str(exc),
            ))
            errors += 1

    db.commit()

    return PriceUpdateOut(
        updated=updated, skipped=skipped, errors=errors,
        results=results,
    )


@app.post("/api/prices/update", response_model=PriceUpdateOut)
def update_prices(db: Session = Depends(get_db)):
    """Aggiorna i prezzi di tutti gli asset che hanno un yahoo_ticker impostato."""
    try:
        return _do_price_update(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# POST /api/rebalance/execute — Salva il ribilanciamento eseguito
# ---------------------------------------------------------------------------
@app.post("/api/rebalance/execute", response_model=RebalanceLogOut, status_code=201)
def execute_rebalance(data: RebalanceLogCreate, db: Session = Depends(get_db)):
    """Registra il ribilanciamento eseguito nel log storico."""
    log = RebalanceLog(
        executed_at=datetime.now(timezone.utc),
        amount=data.amount,
        total_spent=data.total_spent,
        plan_json=json.dumps([item.model_dump() for item in data.plan]),
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return RebalanceLogOut(
        id=log.id,
        executed_at=log.executed_at,
        amount=log.amount,
        total_spent=log.total_spent,
        plan=[RebalancePlanItem(**item) for item in json.loads(log.plan_json)],
    )


# ---------------------------------------------------------------------------
# GET /api/rebalance/history — Storico ribilanciamenti
# ---------------------------------------------------------------------------
@app.get("/api/rebalance/history", response_model=list[RebalanceLogOut])
def get_rebalance_history(db: Session = Depends(get_db)):
    """Restituisce lo storico dei ribilanciamenti (piu' recenti prima, max 50)."""
    logs = (
        db.query(RebalanceLog)
        .order_by(RebalanceLog.executed_at.desc())
        .limit(50)
        .all()
    )
    return [
        RebalanceLogOut(
            id=log.id,
            executed_at=log.executed_at,
            amount=log.amount,
            total_spent=log.total_spent,
            plan=[RebalancePlanItem(**item) for item in json.loads(log.plan_json)],
        )
        for log in logs
    ]


# ---------------------------------------------------------------------------
# GET /api/ticker/search?q=... — Ricerca ticker su Yahoo Finance
# ---------------------------------------------------------------------------
@app.get("/api/ticker/search", response_model=list[TickerSearchResult])
def search_ticker(q: str = Query(..., min_length=2)):
    """Cerca strumenti finanziari su Yahoo Finance per nome o ticker."""
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="yfinance non installato. Esegui: pip install yfinance",
        )

    try:
        search = yf.Search(q, max_results=10)
        quotes = search.quotes if hasattr(search, "quotes") else []
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Errore ricerca Yahoo Finance: {exc}")

    results = []
    for item in quotes:
        results.append(TickerSearchResult(
            symbol=item.get("symbol", ""),
            name=item.get("shortname") or item.get("longname") or item.get("symbol", ""),
            exchange=item.get("exchDisp") or item.get("exchange", ""),
            type=item.get("typeDisp") or item.get("quoteType", ""),
            currency=item.get("currency", ""),
        ))
    return results


# ---------------------------------------------------------------------------
# Serve frontend (must be last, catch-all mount)
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
