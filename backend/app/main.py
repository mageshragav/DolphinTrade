"""DolphinTrade platform - FastAPI entry point.

Lifespan: init DB -> build ML service + agents -> start scheduler ->
start telegram bot. Shuts everything down gracefully on exit.
"""

import asyncio
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.trading.runtime import TradingRuntime
from app.trading.scheduler import Scheduler
from app.connectors.olymp import OlympConnector, token_expiry
from app.connectors.telegram import TelegramBot

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
LOGGER = logging.getLogger('dolphin')

SCHEDULER_TASK = {'task': None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import api  # noqa: F401
    from app.runtime_ctx import RUNTIME
    settings = get_settings()

    await init_db()

    # ML service + agents (reuse the validated pipeline)
    from ml_service import DecisionService
    from agents import NewsAgent, HeadlineAgent, RiskAgent

    ml = DecisionService(theta=settings.theta)
    # load registry champions (if any) so the live pipeline uses validated
    # models; otherwise the bundled static models are used
    try:
        from app.db import SessionLocal
        from app.services import model_registry
        async with SessionLocal() as session:
            rows = await model_registry.list_models(session)
        for r in rows:
            if r['status'] != 'champion':
                continue
            combo = model_registry.parse_combo(r['combo'])
            bundle = model_registry.load_bundle(r['model_path'])
            ml.combo_models[combo] = bundle
            LOGGER.info(f'registry champion loaded for {r["combo"]} '
                        f'(v{r["version"]})')
    except Exception as e:
        LOGGER.warning(f'model registry load failed: {e}')
    news = NewsAgent()
    news.refresh(force=True)
    pairs = [p.strip() for p in settings.pairs.split(',') if p.strip()]
    headlines = HeadlineAgent()
    headlines.refresh(pairs=pairs, force=True)
    risk = RiskAgent()
    if settings.feed == 'csv':
        from app.connectors.csv_feed import CSVFeedConnector
        connector = CSVFeedConnector()
        LOGGER.warning('FEED=csv: simulation mode - decisions recorded, no real bets')
    else:
        connector = OlympConnector()

    runtime = TradingRuntime(ml, news, headlines, risk, connector=connector)
    scheduler = Scheduler(runtime, connector)
    RUNTIME['runtime'] = runtime
    RUNTIME['scheduler'] = scheduler

    # instrument intelligence (live payouts + market schedule) in background
    try:
        from app.connectors import instruments
        asyncio.create_task(asyncio.to_thread(instruments.refresh, True))
    except Exception as e:
        LOGGER.warning(f'instrument refresh launch failed: {e}')

    telegram = TelegramBot()
    telegram.start()
    RUNTIME['telegram'] = telegram

    # session-token health: warn early so auto-trading never dies silently
    try:
        exp = token_expiry()
        if exp is None:
            msg = 'OLYMP SESSION TOKEN MISSING/INVALID - order placement will fail'
            LOGGER.error(msg)
            telegram.send(msg)
        else:
            left_h = (exp - datetime.now(timezone.utc)).total_seconds() / 3600.0
            if left_h < 24:
                msg = (f'OLYMP SESSION TOKEN EXPIRES in {left_h:.0f}h '
                       f'({exp:%Y-%m-%d %H:%M} UTC) - the scheduler will '
                       f'auto-refresh when within 12h of expiry')
                LOGGER.warning(msg)
                telegram.send(msg)
            else:
                LOGGER.info(f'olymp session token valid until {exp:%Y-%m-%d %H:%M} UTC')
    except Exception as e:
        LOGGER.warning(f'token health check failed: {e}')

    SCHEDULER_TASK['task'] = asyncio.create_task(scheduler.run())
    LOGGER.info(f'{settings.app_name} started: combos={settings.combos}, '
                f'dry_run={True}, news={len(news.events)} events')
    try:
        yield
    finally:
        scheduler.stop()
        SCHEDULER_TASK['task'].cancel()
        telegram.stop()
        connector.disconnect()
        LOGGER.info('shutdown complete')


app = FastAPI(title='DolphinTrade', version='1.0.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

from app.api.routes import router as api_router  # noqa: E402

app.include_router(api_router)


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.websocket('/ws')
async def ws_alias(websocket: WebSocket):
    """Alias for /api/ws (frontends may connect to either)."""
    from app import ws as ws_hub
    await ws_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        ws_hub.disconnect(websocket)


# serve the built React frontend when present (registered last so explicit
# API routes keep priority)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FRONTEND_DIST = os.path.join(os.path.dirname(_BACKEND_DIR), 'frontend', 'dist')
if os.path.isdir(_FRONTEND_DIST):
    app.mount('/', StaticFiles(directory=_FRONTEND_DIST, html=True), name='frontend')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host='0.0.0.0',
                port=int(os.environ.get('DT_PORT', '8000')), reload=False)
