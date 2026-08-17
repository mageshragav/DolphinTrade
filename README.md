# DolphinTrade — production trading platform

Multi-agent binary-options platform: live market analysis, real-time news,
ML-gated signals, auto-trading on Olymp Trade, Telegram alerts, and a React
dashboard.

## Stack

- **Backend**: FastAPI (async) + SQLAlchemy 2.0 + PostgreSQL (SQLite in dev)
- **Agents**: LangGraph workflow (market → news → headline/Gemini → risk → orchestrator → execution)
- **ML**: XGBoost multi-timeframe models (5m/15m/30m bars × 15m/30m/1h expiries)
- **Frontend**: React 18 + Vite + TypeScript (served by the backend)
- **Broker**: Olymp Trade websocket (candles + bet placement + verification)
- **Alerts**: Telegram bot (signals + `/status /trades /stop /start /limits`)

## Quick start (docker)

```bash
cp .env.example .env        # set GEMINI key, telegram token, adjust limits
docker compose up --build
# UI:  http://localhost:8000
```

Everything starts in **DRY-RUN** — signals are logged but no real bets are
placed. Flip `DT_DRY_RUN=false` (or the Settings panel in the UI) only after
paper validation.

## Quick start (local dev)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --port 8000        # API + dashboard

cd frontend
npm install && npm run dev                     # dev server with proxy
```

Uses SQLite by default (`dolphintrade.db`); set `DT_DATABASE_URL` for Postgres.

## Architecture

```
React UI ──WS──► FastAPI ──► LangGraph workflow
                       │          ├─ market agent   (8 combo models)
                       │          ├─ news agent     (live ForexFactory)
                       │          ├─ headline agent (Google News + Gemini)
                       │          ├─ risk agent     (fakeout/spread checks)
                       │          └─ orchestrator → execution
                       ├─ scheduler  (5m/15m/30m/1h boundaries)
                       ├─ execution  (idempotency, risk limits, dry-run)
                       ├─ tracker    (settle at expiry, circuit breaker)
                       └─ telegram   (signal alerts + operator commands)
```

## Safety rails (all live-adjustable in the UI / `/stop` on Telegram)

- Dry-run mode (default ON)
- Kill switch (blocks all bets instantly)
- Max trades/day, max daily loss %, per-symbol cooldown
- Idempotency: duplicate signals are never double-placed
- Circuit breaker: pauses when realized win rate drifts from projected

## API surface

| Endpoint | Purpose |
|---|---|
| `GET /api/monitor/status` | runtime state, limits, circuit breaker |
| `POST /api/monitor/control` | `{"action": "start"\|"stop"}` scheduler |
| `POST /api/monitor/kill` | `{"on": true\|false}` kill switch |
| `GET /api/decisions` · `/api/trades` · `/api/signals` | history |
| `GET /api/agents` · `/api/agent-events` | agent context + LLM trail |
| `GET/PUT /api/settings` | risk limits + trading config |
| `WS /api/ws` | real-time events (decisions, trades, alerts) |
| `GET /health` | liveness |

## Tests

```bash
cd backend && python -m pytest tests/ -q     # 5 passed
```

## Research code

The `backend/dolphin/` directory holds the validated research pipeline
(feature engineering, walk-forward validation, the 8 combo models). The
platform reuses it via `ml_service.py` + `agents.py` — the model files live
in `backend/dolphin/common/ml_model/`.
