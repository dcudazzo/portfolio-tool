# Portfolio Tracker — Changelog

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

### 11.1 Gestione strategia dinamica
- [ ] Aggiungere tabella `strategies` nel DB (nome, descrizione, target % per ETF)
- [ ] Permettere creazione di piu strategie (es. "Aggressiva 20Y", "Moderata 10Y", "Pre-pensione")
- [ ] Switch tra strategie dall'interfaccia
- [ ] Il ribilanciamento usa sempre la strategia attiva corrente
- [ ] Storico delle strategie applicate nel tempo (con date di attivazione)

### 11.2 Gestione liquidita
- [ ] Aggiungere voce "Liquidita" al portafoglio (conto corrente, conto deposito, money market)
- [ ] Inserimento manuale e aggiornamento periodico
- [ ] Conteggio nel patrimonio totale e targetabile in percentuale
- [ ] Il calcolatore di ribilanciamento tiene conto della liquidita disponibile e target
- [ ] Visualizzazione separata: "Patrimonio investito" vs "Liquidita" vs "Totale patrimonio"

### 11.3 Nuovi strumenti e asset class
- [ ] Aggiunta dinamica di nuovi ETF/asset class dall'interfaccia (nome, ticker, ISIN, PMC, qty)
- [ ] Supporto per asset class non-ETF: azioni singole, obbligazioni dirette, crypto, immobiliare
- [ ] Campo "tipo" per ogni strumento (ETF, ETC, azione, crypto, liquidita) con icone differenziate

### 11.4 Altre evoluzioni
- [ ] Importazione automatica prezzi tramite API Yahoo Finance (aggiornamento con un click)
- [ ] Alert su Telegram quando un ETF supera soglia di deviazione dal target (es. +/-5%)
- [ ] Calcolo TWR (Time-Weighted Return) per performance corretta dai flussi di cassa
- [ ] Export CSV/PDF del report periodico con snapshot e riepilogo ribilanciamenti
- [ ] Proiezione Monte Carlo a 20 anni con simulazione rendimenti attesi
- [ ] Log storico di tutti i ribilanciamenti eseguiti (data, importo, quote acquistate)
