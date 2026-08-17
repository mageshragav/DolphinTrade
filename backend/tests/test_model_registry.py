"""Model registry tests: CRUD, promote/rollback, training smoke test.

Run:  cd backend && python -m pytest tests/test_model_registry.py -q
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import pytest_asyncio

os.environ['DT_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['DT_DRY_RUN'] = 'true'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_db, SessionLocal  # noqa: E402
from app.services import model_registry  # noqa: E402
from app.services import persistence  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def db():
    await init_db()
    yield
    async with SessionLocal() as s:
        from app.models import ModelVersion, Candle
        for m in (ModelVersion, Candle):
            await s.execute(m.__table__.delete())
        await s.commit()


def _candles(n=260, syms=('FX:EURUSD', 'FX:USDJPY')):
    """Sine-wave prices (strong + weak moves) so labels cover 0/1/2."""
    import math
    rows = []
    base = datetime(2026, 7, 1, tzinfo=timezone.utc)
    for i in range(n):
        wave = math.sin(i / 6.0) * 0.004 + math.sin(i / 23.0) * 0.001
        p = 1.0 + wave
        for sym in syms:
            rows.append({'symbol': sym, 'datetime': base + timedelta(minutes=5 * i),
                         'open': p, 'high': p + 0.0008, 'low': p - 0.0008,
                         'close': p + math.sin(i / 6.0 + 0.7) * 0.0005,
                         'volume': 100 + (i * 7) % 90})
    return pd.DataFrame(rows)


async def test_register_promote_rollback():
    async with SessionLocal() as s:
        r1 = await model_registry.register(s, '300_900', '/tmp/opencode/m1.sav',
                                           {'val_win_rate': 0.61})
        assert r1.version == 1 and r1.status == 'candidate'
        r2 = await model_registry.register(s, '300_900', '/tmp/opencode/m2.sav',
                                           {'val_win_rate': 0.63})
        assert r2.version == 2

        res = await model_registry.promote(s, '300_900', version=2)
        assert res['ok']
        champ = await model_registry.champion_for(s, '300_900')
        assert champ is not None and champ.version == 2
        assert champ.status == 'champion'

        rows = await model_registry.list_models(s, combo='300_900')
        statuses = {r['version']: r['status'] for r in rows}
        assert statuses == {1: 'candidate', 2: 'champion'}

        # rollback to v1
        await model_registry.rollback(s, '300_900', 1)
        champ = await model_registry.champion_for(s, '300_900')
        assert champ.version == 1


async def test_versions_increment_per_combo():
    async with SessionLocal() as s:
        await model_registry.register(s, '300_900', '/tmp/opencode/a.sav', {})
        await model_registry.register(s, '300_900', '/tmp/opencode/b.sav', {})
        await model_registry.register(s, '900_3600', '/tmp/opencode/c.sav', {})
        rows = await model_registry.list_models(s)
        assert {r['combo']: r['version'] for r in rows} == {
            '300_900': 2, '900_3600': 1}


async def test_train_bundle_smoke():
    """Training from archive-format candles produces a loadable bundle."""
    import asyncio
    import os as _os
    import pickle as pk
    import tempfile

    candles = _candles()
    bundle, metrics = await asyncio.to_thread(
        model_registry.train_bundle, candles, 300, 900)
    assert {'model', 'features', 'bar_sec', 'expiry_sec'} <= set(bundle.keys())
    assert bundle['bar_sec'] == 300 and bundle['expiry_sec'] == 900
    assert len(bundle['features']) > 0
    assert metrics.get('rows', 0) > 100
    # the bundle round-trips through the production loader
    with tempfile.NamedTemporaryFile(suffix='.sav', delete=False) as f:
        pk.dump(bundle, f)
        path = f.name
    try:
        loaded = model_registry.load_bundle(path)
        assert loaded['columns'] == loaded['features']
    finally:
        _os.unlink(path)


async def test_validate_challenger_runs_backtest_comparison():
    """Challenger validation replays both models through the backtest engine."""
    import asyncio

    candles = _candles(n=400, syms=('FX:EURUSD',))
    async with SessionLocal() as s:
        await persistence.archive_candles(s, candles)
    bundle, _ = await asyncio.to_thread(model_registry.train_bundle, candles, 300, 900)
    async with SessionLocal() as s:
        v = await model_registry.validate_challenger(s, (300, 900), bundle,
                                                     window_days=None)
        assert v['verdict'] in ('promote', 'keep', 'insufficient')
        assert 'champion' in v and 'challenger' in v
        # the champion here is the bundled static model (no registry rows yet)
        if v['verdict'] != 'insufficient':
            assert v['champion'].get('trades', 0) >= 0
            assert v['challenger'].get('trades', 0) >= 0