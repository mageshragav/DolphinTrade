"""DolphinTrade platform configuration (env-driven).

Defaults keep the system safe: DRY_RUN=true, tight risk limits.
All secrets come from environment variables (docker-compose / .env).
"""

import os
import sys
from functools import lru_cache

from pydantic_settings import BaseSettings

# make the existing research modules importable (dolphin/ package)
DOLPHIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dolphin')
# Import the OUTER dolphin package BEFORE inserting its dir on sys.path: with
# backend/dolphin at path[0] first, `import dolphin` would bind to the nested
# backend/dolphin/dolphin (Django) package and dolphin.ml_service etc. become
# unimportable. Importing it first (backend is already importable here) pins
# the correct outer package; the insert below then only serves the legacy
# `common.*` / `dolphin.*` imports used by the research scripts.
import dolphin  # noqa: F401
if DOLPHIN_DIR not in sys.path:
    sys.path.insert(0, DOLPHIN_DIR)


class Settings(BaseSettings):
    app_name: str = 'DolphinTrade'
    debug: bool = False

    # database
    database_url: str = 'sqlite+aiosqlite:///./dolphintrade.db'

    # broker / feed
    olymp_group: str = 'demo'                    # demo | real
    olymp_pair_suffix: str = ''                  # '' = normal market (EURUSD)
                                                 # '_OTC' only if the broker
                                                 # rejects plain pairs again
    feed: str = 'olymp'                          # olymp | csv (simulation replay)

    # telegram
    telegram_bot_token: str = ''
    telegram_chat_id: str = ''
    telegram_group_id: str = ''

    # llm
    gemini_api_key: str = ''

    # trading defaults
    theta: float = 0.65
    dry_run: bool = True
    stake_pct: float = 0.01
    max_trades_per_day: int = 10
    max_daily_loss_pct: float = 5.0
    symbol_cooldown_min: int = 30
    combos: str = '5m:15m,5m:30m,5m:1h,15m:1h,30m:1h'
    hours_window: str = 'all'                    # e.g. '15-17'
    pairs: str = 'EURUSD,EURJPY,GBPUSD,USDCAD,USDJPY,EURAUD,EURCAD,EURGBP'
    equity: float = 1000.0

    # circuit breaker
    drift_tolerance_pts: float = 4.0
    drift_min_trades: int = 50

    # hourly minimum-signal guarantee
    hourly_guarantee: bool = True      # pick the best candidate at :minute
    hourly_minute: int = 55            # scan minute within the hour

    class Config:
        env_prefix = 'DT_'
        env_file = '.env'
        extra = 'ignore'


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # fall back to the values embedded in the existing constants module
    if not s.telegram_bot_token or not s.telegram_group_id:
        try:
            from common.constants import BOT_TOKEN, GROUP_ID
            s.telegram_bot_token = s.telegram_bot_token or BOT_TOKEN
            s.telegram_group_id = s.telegram_group_id or GROUP_ID
        except Exception:
            pass
    return s
