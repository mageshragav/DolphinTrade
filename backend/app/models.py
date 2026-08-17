"""ORM models: decisions, trades, agent events, signals, settings."""

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Decision(Base):
    __tablename__ = 'decisions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    tf: Mapped[str] = mapped_column(String(8), default='5m')
    expiry: Mapped[str] = mapped_column(String(8), default='15m')
    action: Mapped[str] = mapped_column(String(8), index=True)      # CALL | PUT | NEUTRAL
    p_call: Mapped[float] = mapped_column(Float, default=0.0)
    p_put: Mapped[float] = mapped_column(Float, default=0.0)
    best_prob: Mapped[float] = mapped_column(Float, default=0.0)
    ev_score: Mapped[float] = mapped_column(Float, default=0.0)
    candle_close: Mapped[str] = mapped_column(String(32), default='')
    candle_open: Mapped[float] = mapped_column(Float, nullable=True)
    candle_high: Mapped[float] = mapped_column(Float, nullable=True)
    candle_low: Mapped[float] = mapped_column(Float, nullable=True)
    candle_close_price: Mapped[float] = mapped_column(Float, nullable=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=True)
    target_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=True)
    atr: Mapped[float] = mapped_column(Float, nullable=True)
    sentiment_bias: Mapped[str] = mapped_column(String(12), default='neutral')
    manipulation_risk: Mapped[str] = mapped_column(String(8), default='low')
    news_veto: Mapped[bool] = mapped_column(Boolean, default=False)
    news_next: Mapped[str] = mapped_column(String(120), nullable=True)
    headline: Mapped[str] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(40), default='')
    rationale: Mapped[str] = mapped_column(Text, default='')
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)


class Trade(Base):
    __tablename__ = 'trades'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(Integer, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    tf: Mapped[str] = mapped_column(String(8), default='5m')
    expiry: Mapped[str] = mapped_column(String(8), default='15m')
    action: Mapped[str] = mapped_column(String(8))
    candle_open: Mapped[float] = mapped_column(Float, nullable=True)
    candle_close: Mapped[float] = mapped_column(Float, nullable=True)
    entry: Mapped[float] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=True)
    expiry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    candle_close_ts: Mapped[str] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default='open', index=True)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    result: Mapped[str] = mapped_column(String(8), nullable=True)
    broker_ref: Mapped[str] = mapped_column(String(64), nullable=True)
    broker_status: Mapped[str] = mapped_column(String(24), nullable=True)
    winperc: Mapped[float] = mapped_column(Float, nullable=True)
    order_type: Mapped[str] = mapped_column(String(12), default='binary')
    placed_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    stake: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default='')


class AgentEvent(Base):
    __tablename__ = 'agent_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)   # news | sentiment | risk | system
    symbol: Mapped[str] = mapped_column(String(16), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default='')
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)


class Signal(Base):
    __tablename__ = 'signals'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    expiry: Mapped[str] = mapped_column(String(8))
    action: Mapped[str] = mapped_column(String(8))
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    telegram_status: Mapped[str] = mapped_column(String(12), default='pending')
    trade_id: Mapped[int] = mapped_column(Integer, nullable=True)


class BotSetting(Base):
    __tablename__ = 'bot_settings'

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
