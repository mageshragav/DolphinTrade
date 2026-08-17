"""Async SQLAlchemy engine/session + ORM base."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str = None):
    url = url or get_settings().database_url
    kwargs = {}
    if url.startswith('sqlite'):
        kwargs['connect_args'] = {'check_same_thread': False}
    return create_async_engine(url, echo=False, **kwargs)


engine = make_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db():
    from app import models  # noqa: F401  (register tables)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # lightweight migrations for existing databases
    await _ensure_column(engine, 'trades', 'broker_status', 'VARCHAR(24)')
    await _ensure_column(engine, 'trades', 'winperc', 'FLOAT')
    await _ensure_column(engine, 'trades', 'order_type', 'VARCHAR(12)')
    await _ensure_column(engine, 'trades', 'candle_close_ts', 'VARCHAR(32)')


async def _ensure_column(engine_, table: str, column: str, ddl_type: str):
    try:
        from sqlalchemy import text
        async with engine_.begin() as conn:
            if engine_.url.drivername.startswith('sqlite'):
                cols = await conn.execute(text(f'PRAGMA table_info({table})'))
                names = {r[1] for r in cols}
                if column not in names:
                    await conn.execute(text(
                        f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))
            else:
                cols = await conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{table}'"))
                names = {r[0] for r in cols}
                if column not in names:
                    await conn.execute(text(
                        f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))
    except Exception as e:
        logging.getLogger('dolphin').warning(f'migration {table}.{column} skipped: {e}')
