"""Candle archive tests: idempotent writes, load/query, stats.

Run:  cd backend && python -m pytest tests/test_candle_archive.py -q
"""

import os
import sys
from datetime import datetime, timezone

import pandas as pd
import pytest
import pytest_asyncio

os.environ['DT_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['DT_DRY_RUN'] = 'true'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_db, SessionLocal  # noqa: E402
from app.services import persistence  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def db():
    await init_db()
    yield
    async with SessionLocal() as s:
        from app.models import Candle
        await s.execute(Candle.__table__.delete())
        await s.commit()


def _frame(symbols=('FX:EURUSD', 'FX:USDJPY'), n=5, start=None):
    if start is None:
        start = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        t = start.timestamp() + i * 300
        for sym in symbols:
            rows.append({'t': t, 'o': 1.0 + i, 'h': 1.1 + i, 'l': 0.9 + i,
                         'c': 1.05 + i, 'v': 100 + i, 'symbol': sym})
    return pd.DataFrame(rows)


async def test_archive_wire_frame_and_load():
    async with SessionLocal() as s:
        n = await persistence.archive_candles(s, _frame())
        assert n == 10
        df = await persistence.load_candles(s)
        assert len(df) == 10
        assert {'symbol', 'datetime', 'open', 'high', 'low', 'close', 'volume'} \
            <= set(df.columns)
        assert df['symbol'].nunique() == 2
        assert df['datetime'].dt.tz is not None  # UTC-aware


async def test_archive_is_idempotent():
    async with SessionLocal() as s:
        n1 = await persistence.archive_candles(s, _frame())
        n2 = await persistence.archive_candles(s, _frame())
        assert n1 == 10 and n2 == 0
        df = await persistence.load_candles(s)
        assert len(df) == 10


async def test_archive_partial_overlap():
    async with SessionLocal() as s:
        await persistence.archive_candles(s, _frame(n=5))
        n = await persistence.archive_candles(s, _frame(n=7))  # 2 new bars
        assert n == 4  # 7 bars x 2 symbols - 10 existing = 4
        assert len(await persistence.load_candles(s)) == 14


async def test_load_symbol_and_window_filters():
    async with SessionLocal() as s:
        await persistence.archive_candles(s, _frame(n=5))
        only_eur = await persistence.load_candles(s, symbols=['FX:EURUSD'])
        assert only_eur['symbol'].nunique() == 1
        start = datetime(2026, 8, 1, 0, 5, tzinfo=timezone.utc)
        after = await persistence.load_candles(s, symbols=['FX:EURUSD'], start=start)
        assert len(after) == len(only_eur[only_eur['datetime'] >= start])


async def test_archive_accepts_normalized_frame():
    async with SessionLocal() as s:
        raw = _frame(symbols=('FX:EURUSD',), n=3)
        raw = raw.rename(columns={'t': 'datetime', 'o': 'open', 'h': 'high',
                                  'l': 'low', 'c': 'close', 'v': 'volume'})
        raw['datetime'] = pd.to_datetime(raw['datetime'], unit='s', utc=True)
        n = await persistence.archive_candles(s, raw)
        assert n == 3
        assert len(await persistence.load_candles(s)) == 3


async def test_candle_stats():
    async with SessionLocal() as s:
        await persistence.archive_candles(s, _frame(n=5))
        stats = await persistence.candle_stats(s)
        assert stats['total_candles'] == 10
        assert stats['symbols'] == 2
        assert 'FX:EURUSD' in stats['by_symbol']
        assert stats['by_symbol']['FX:EURUSD']['count'] == 5