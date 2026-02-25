# Portfolio Tracker — Changelog

## v1.3 — 2026-02-25

### 11.3 Nuovi strumenti e asset class
- [x] Rinomina tabella `etfs` in `assets` con migrazione automatica al primo avvio
- [x] Nuovo campo `type` (etf, etc, azione, crypto, obbligazione) con badge colorato nel dashboard
- [x] Nuovo campo `isin` (opzionale) per codice ISIN
- [x] Nuovo campo `yahoo_ticker` (opzionale) per aggiornamento prezzi automatico
- [x] `POST /api/assets` — aggiunge un nuovo strumento con validazione tipo e id unico
- [x] `DELETE /api/assets/{id}` — elimina strumento (protegge ultimo asset, pulisce strategie)
- [x] `PUT /api/assets/{id}` — aggiorna prezzo, PMC, qty, yahoo_ticker, isin, tipo
- [x] Frontend: form "Aggiungi nuovo strumento" nella tab Impostazioni
- [x] Frontend: pulsante "Elimina" per ogni asset con conferma
- [x] Frontend: campo "Ticker Yahoo" editabile per ogni asset
- [x] Frontend: badge tipo (ETF/ETC/AZ/CRYPTO/OBB) nel dashboard e impostazioni
- [x] Auto-genera id dal nome (slug alfanumerico, max 10 caratteri)
- [x] Migrazione: gold automaticamente impostato come tipo "etc"

### 11.4 Yahoo Finance (parziale)
- [x] Nuova dipendenza `yfinance` in requirements.txt
- [x] `POST /api/prices/update` — aggiorna prezzi via Yahoo Finance per tutti gli asset con yahoo_ticker
- [x] Conversione automatica USD/GBP in EUR tramite tassi di cambio yfinance
- [x] `GET /api/ticker/search?q=...` — ricerca strumenti su Yahoo Finance (ETF, azioni, crypto, futures)
- [x] Schema `TickerSearchResult` (symbol, name, exchange, type, currency)
- [x] Frontend: pulsante "Aggiorna prezzi" nell'header
- [x] Frontend: toast con risultato aggiornamento (aggiornati/saltati/errori)
- [x] Frontend: indicatore "Ultimo aggiornamento" sotto il totale
- [x] Frontend: barra di ricerca ticker nel form "Aggiungi nuovo strumento"
- [x] Frontend: click su risultato compila automaticamente nome, ticker, yahoo_ticker e tipo

## v1.2 — 2026-02-22

### 11.1 Gestione strategia dinamica
- [x] Nuovo modello `Strategy` nel database (name, description, targets_json, is_active, activated_at)
- [x] Nuovo modello `StrategyHistory` per log attivazioni (strategy_name, activated_at)
- [x] Seed automatico: strategia "Predefinita" creata dai target iniziali al primo avvio
- [x] `GET /api/strategies` — lista tutte le strategie salvate
- [x] `POST /api/strategies` — crea nuova strategia con validazione somma target = 100%
- [x] `PUT /api/strategies/{id}` — modifica nome, descrizione o target di una strategia
- [x] `DELETE /api/strategies/{id}` — elimina strategia (protegge quella attiva)
- [x] `POST /api/strategies/{id}/activate` — attiva strategia, copia target su ETF/Cash, logga storico
- [x] `GET /api/strategies/history` — storico attivazioni ordine cronologico inverso
- [x] `PUT /api/targets` sincronizza automaticamente la strategia attiva quando si salvano i target
- [x] Frontend: card "Strategie di allocazione" nella tab Impostazioni
- [x] Frontend: lista strategie con badge "Attiva", pulsanti Attiva/Elimina
- [x] Frontend: form creazione nuova strategia (nome + descrizione, usa target correnti)
- [x] Frontend: attivazione strategia aggiorna immediatamente slider e dashboard
- [x] Frontend: storico attivazioni (ultime 10) con data/ora

## v1.1 — 2026-02-21

### 11.2 Gestione liquidita
- [x] Nuovo modello `Cash` nel database (amount, target_pct)
- [x] Endpoint `PUT /api/cash` per aggiornare importo e target liquidita
- [x] `GET /api/portfolio` include campo `liquidity` con amount, target_pct, weight_pct
- [x] `PUT /api/targets` accetta chiave `cash` per il target liquidita
- [x] `GET /api/rebalance` include `liquidity_after` nella risposta
- [x] `GET /api/summary` include liquidita in pesi e target
- [x] Totali portafoglio (total_value, total_invested) includono la liquidita
- [x] Dashboard: riga "Liquidita" con bordo tratteggiato, peso %, 0% gain
- [x] Dashboard: barra peso liquidita con target line
- [x] Ribilanciamento: mostra "Liquidita dopo il ribilanciamento" nei risultati
- [x] Impostazioni: sezione dedicata per editare importo liquidita
- [x] Impostazioni: slider target liquidita incluso nella validazione somma=100%

## v1.0 — 2026-02-21

### Struttura progetto
- Creata architettura `backend/` + `frontend/` come da specifica
- File systemd `portfolio-tracker.service` per deploy su Proxmox LXC

### Backend (FastAPI + SQLite)
- **database.py** — Connessione SQLite via SQLAlchemy, session factory
- **models.py** — Tabelle `etfs` (id, name, ticker, qty, pmc, price, target_pct, updated_at) e `snapshots` (id, date, total_value, total_invested, created_at)
- **schemas.py** — Pydantic schemas per validazione input/output di tutti gli endpoint
- **main.py** — FastAPI app con:
  - Seed automatico del database al primo avvio con i 5 ETF del portafoglio Fineco
  - `GET /api/portfolio` — Restituisce tutti gli ETF con valori calcolati (gain EUR/%, peso %, delta vs target)
  - `PUT /api/etf/{id}` — Aggiorna prezzo mercato, PMC o quantita di un singolo ETF
  - `PUT /api/targets` — Aggiorna target allocation % con validazione somma = 100%
  - `GET /api/rebalance?amount=N` — Calcola piano ribilanciamento (quote intere, no vendite, Bond 7-10Y escluso)
  - `GET /api/snapshots` — Lista snapshot performance ordinati per data
  - `POST /api/snapshots` — Aggiunge snapshot (data, valorizzazione, versato)
  - `DELETE /api/snapshots/{id}` — Elimina uno snapshot
  - `GET /api/summary` — KPI aggregati (totale, gain, pesi attuali vs target)
  - Serving statico del frontend da `../frontend/`
- **requirements.txt** — fastapi 0.115.6, uvicorn 0.34.0, sqlalchemy 2.0.36, pydantic 2.10.4

### Frontend (index.html)
- Partito dal frontend esistente (`portfolio-tracker.html`) con localStorage
- Sostituito tutte le funzioni `load()`/`save()` con chiamate `fetch()` asincrone alle API REST
- Aggiunto layer API centralizzato (`async function api()`) con gestione errori HTTP
- Aggiunto loading spinner overlay durante le chiamate di rete
- Aggiunto sistema di notifiche toast (successo verde / errore rosso)
- Tabs ora ricaricano i dati dal backend ad ogni switch
- Settings: aggiornamento ETF invia `PUT /api/etf/{id}` per ogni ETF modificato
- Settings: salvataggio target invia `PUT /api/targets`
- Performance: snapshot gestiti tramite `POST`/`DELETE` `/api/snapshots`
- Ribilanciamento: calcolo delegato al backend via `GET /api/rebalance?amount=N`

### Deploy
- Systemd unit file (`portfolio-tracker.service`) pronto per `/opt/portfolio-tracker/` su LXC Ubuntu
- Accesso via Tailscale su porta 8000, nessun reverse proxy necessario

---

## Next steps — Evoluzioni future (da specifica, sezione 11)

### ~~11.1 Gestione strategia dinamica~~ (completato in v1.2)

### ~~11.2 Gestione liquidita~~ (completato in v1.1)

### ~~11.3 Nuovi strumenti e asset class~~ (completato in v1.3)

### 11.4 Altre evoluzioni
- [x] ~~Importazione automatica prezzi tramite API Yahoo Finance (aggiornamento con un click)~~ (completato in v1.3)
- [ ] Alert su Telegram quando un ETF supera soglia di deviazione dal target (es. +/-5%)
- [ ] Calcolo TWR (Time-Weighted Return) per performance corretta dai flussi di cassa
- [ ] Export CSV/PDF del report periodico con snapshot e riepilogo ribilanciamenti
- [ ] Proiezione Monte Carlo a 20 anni con simulazione rendimenti attesi
- [ ] Log storico di tutti i ribilanciamenti eseguiti (data, importo, quote acquistate)
