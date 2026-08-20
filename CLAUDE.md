# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

DolphinTrade is a multi-agent binary-options trading platform (Olymp Trade broker): live market analysis, ML-gated signals (XGBoost, multi-timeframe), a LangGraph agent workflow (market → news → headline/Gemini sentiment → risk → orchestrator → execution), Telegram alerts, and a React dashboard served by the backend. Everything defaults to **DRY-RUN** (`DT_DRY_RUN=true`) — no real bets are placed until this is explicitly flipped off.

See root `README.md` for the product-level architecture diagram, API surface table, and safety-rail summary — this file focuses on what's needed to work in the code.

## Commands

### Local dev
```bash
cd backend && uv sync
uv run uvicorn app.main:app --port 8000     # API + dashboard, http://localhost:8000

cd frontend && npm install && npm run dev   # Vite dev server on :5173, proxies /api and /ws to :8001
```
Note the port mismatch: `uvicorn` above binds `:8000`, but `frontend/vite.config.ts` proxies to `:8001` — align the port you run the backend on with the proxy target (or edit the proxy) when doing frontend dev against a local backend.

### Docker (full stack incl. Postgres)
```bash
cp .env.example .env        # set secrets: Gemini key, Olymp creds, Telegram token
docker compose up --build   # UI at http://localhost:8000 (or $DT_PORT)
```

### Tests
```bash
cd backend && python -m pytest tests/ -q
```
`backend/conftest.py` forces `import dolphin` / `import dolphin.ml_service` before test collection — this is load-bearing, not incidental (see Gotchas below).

### Lint/format
None configured. No ruff/black/mypy in `backend/pyproject.toml`, and no ESLint/test config in `frontend/`. Don't assume a lint step exists or invent one.

## Architecture

### Two backend packages: `app/` vs `dolphin/`
`backend/dolphin/` is the original Django-based research monolith (full Django project under `dolphin/dolphin/` with `settings.py`/`asgi.py`/`celery.py`, plus Django sub-apps `common`, `tradingasset`, `TradingDataGeneration`, `TradingStradegy`, `users`). `backend/app/` is the newer production FastAPI runtime, which **imports and reuses `dolphin/`'s validated ML pipeline as a library** rather than duplicating it — mainly `dolphin/ml_service.py` (production `DecisionService`), `dolphin/multi_tf_models.py` (training/walk-forward), and `dolphin/features/mql_signals.py` (MQL-derived technical features). `backend/app/config.py` documents the sys.path handling needed so `dolphin.*` imports resolve correctly instead of being shadowed by the nested `dolphin/dolphin` Django package.

When touching ML/feature logic, check `dolphin/` first — much of `dolphin/` outside `ml_service.py`/`multi_tf_models.py`/`features/` (the Django apps, `live_loop.py`, `phase0/1/2_validation.py`, `MT4Algorithms/` notebooks) is legacy/research code no longer in the live path. Note also: `dolphin/MT4Algorithms/` is Jupyter notebooks only, and `features/mql_signals.py` is the entire extent of "MT4" integration — there is no live MT4/MQL bridge; it's technical-indicator logic ported from MQL.

### `backend/app/` — production runtime
- `app/main.py` — FastAPI app, lifespan wiring (DB, ML `DecisionService`, agents, connector, `TradingRuntime`, `Scheduler`, Telegram bot), serves `frontend/dist` as static files.
- `app/api/routes.py` — all REST + `/api/ws` websocket endpoints.
- `app/trading/graph.py` — LangGraph workflow (`TradeState`): market → news → headline/sentiment → risk → orchestrator → execution, invoked per (symbol, combo) candidate.
- `app/trading/runtime.py` — `TradingRuntime.cycle()`: fetch candles → classify regime → `ml.decide_all` → run graph per candidate → settle → broadcast WS. Also `hourly_scan()` (hourly minimum-signal guarantee).
- `app/trading/scheduler.py` — boundary-aligned loop; also drives token auto-renew, drift-check/auto-disable, nightly report, weekly champion/challenger retrain.
- `app/services/regime.py` — regime classifier (trend/range/high_vol/mixed) that adjusts the `theta` probability gate; also normalizes broker OHLCV column names.
- `app/services/risk.py` — all guardrails: dry-run/kill-switch, daily trade/loss limits, cooldowns, portfolio stake caps (`max_concurrent`, `max_stake_in_flight_pct`), per-combo drift monitor + auto-disable, circuit breaker.
- `app/services/model_registry.py` — champion/challenger lifecycle: `train_bundle()`, `validate_challenger()`, `promote()`/`rollback()`; bundles under `dolphin/common/ml_model/challengers/`.
- `app/backtest/engine.py` — walk-forward backtest replaying archived candles through the same production decision path; used both for user-triggered backtests and challenger validation.
- `app/connectors/olymp.py` — Olymp Trade websocket connector (candles, bet placement, JWT session handling); `csv_feed.py` is the offline/simulation replay feed (`FEED=csv`).

### Frontend
React 18 + TypeScript + Vite, deliberately dependency-light: **no charting library** (hand-rolled inline SVG in `Candles.tsx`/`Analytics.tsx`/`TradeDrawer.tsx`), **no state library** (state lives in `App.tsx` via hooks, passed down as props), **no router** (hash-based routing, `location.hash` parsed against a fixed `Page` union in `Sidebar.tsx`), **no UI kit** (`src/components/ui.tsx` primitives + `src/index.css` with CSS-var dark/light theming). API calls go through `src/api.ts` (`get`/`post`/`put` over `fetch`, relative paths only, no base-URL env var); live updates via `src/ws.ts` (`useWebSocket`, connects to `/api/ws`) combined with a 10s polling refresh in `App.tsx`. Dev proxy in `vite.config.ts` sends `/api` and `/ws` to `http://localhost:8001`.

### Config
Settings load via `pydantic-settings` with `env_prefix='DT_'` (`app/config.py`); the legacy `dolphin/` modules load secrets separately via `dolphin/common/constants.py`. See `.env.example` for the full variable list (trading limits, Gemini key, Telegram, Olymp credentials/session tokens, database URL).

## Gotchas / conventions worth knowing

- **`backend/requirements.txt` vs `backend/pyproject.toml`/`uv.lock`**: Docker installs from `requirements.txt` (the trimmed FastAPI/ML set); local dev uses `uv sync` against `pyproject.toml`. Keep both in sync when adding a runtime dependency the Docker image needs. `pyproject.toml` also still carries legacy Django-era pins (`Django`, `celery`, `mysqlclient`, `gspread`, etc.) for the old `dolphin/dolphin` app — its `description` field ("DolphinTrade Django backend") is stale; the live system is FastAPI.
- **Secrets**: never hardcode Olymp JWTs or the Telegram bot token in source — they belong only in the gitignored `backend/.env`. `backend/scripts/check_secrets.py` is a pre-commit guard for this (wire via `.git/hooks/pre-commit`, see its docstring) — run it manually if you're unsure whether a diff you're about to commit contains a live token.
- **Olymp session tokens** expire and are renewed by `backend/scripts/refresh_token.py` (drives a headless Chrome session against the broker's own login page, not a documented OAuth flow) — triggered automatically by `Scheduler` when the token is within 12h of expiry, or runnable manually with `--push http://host:port` to hot-swap a running server's token without restart.
- **Test import order matters**: `backend/conftest.py` forces `dolphin`/`dolphin.ml_service` to import before test collection to avoid the `dolphin` namespace package resolving to the nested Django `dolphin/dolphin` package instead of the top-level research package. If backend tests start failing with confusing `dolphin.*` import errors, check this first before assuming a code bug.
- Root-level `stradegy.py` and `mt4indicators/` are scratch/reference material (MQL indicator scripts, an old extremes-detection script), not part of the running application.
