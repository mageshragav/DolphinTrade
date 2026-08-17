export interface Decision {
  id?: number; ts?: string; symbol: string; tf: string; expiry: string;
  action: 'CALL' | 'PUT' | 'NEUTRAL'; p_call?: number; p_put?: number;
  best_prob?: number; ev_score?: number; candle_close?: string;
  candle_open?: number | null; candle_close_price?: number | null;
  entry_price?: number | null; target_price?: number | null;
  stop_loss?: number | null; atr?: number | null;
  sentiment_bias?: string; manipulation_risk?: string;
  news_veto?: boolean; news_next?: string | null; headline?: string | null;
  model?: string; rationale?: string;
}

export interface Trade {
  id: number; ts?: string; symbol: string; tf: string; expiry: string;
  action: 'CALL' | 'PUT'; candle_open?: number | null; candle_close?: number | null;
  entry?: number | null; take_profit?: number | null; stop_loss?: number | null;
  expiry_time?: string | null; status: string; exit_price?: number | null;
  result?: string | null; broker_ref?: string | null; dry_run: boolean;
  stake?: number; reason?: string;
}

export interface MonitorStatus {
  running: boolean; kill_switch: boolean; dry_run: boolean;
  trades_today: number; losses_today: number;
  max_trades_per_day: number; max_daily_loss_pct: number;
  circuit_breaker: { sample: number; paused: boolean; win_rate: number | null;
                     projected: number | null; status: string };
  theta: number; combos: string; hours_window: string; pairs: string;
  equity: number; stake_pct: number; model_count: number; news_events: number;
  token_ok?: boolean; token_expires_at?: string | null;
}

export interface AgentsStatus {
  news_events: number; sentiment: Record<string, string>;
  next_event: string | null; next_event_time: string | null; llm: boolean;
}

export interface Settings {
  dry_run: boolean; max_trades_per_day: number; max_daily_loss_pct: number;
  symbol_cooldown_min: number; stake_pct: number; equity: number;
  order_type: 'binary' | 'multiplier'; order_types: ('binary' | 'multiplier')[]; multiplicator: number;
  sl_tp_mode: 'signal_levels' | 'atr'; atr_sl_mult: number; atr_tp_mult: number;
  hw_stop_pct: number; daily_profit_target_pct: number;
  loss_streak_reduce_after: number; loss_streak_stake_factor: number;
  news_blackout_min: number;
  hourly_floor: number; hourly_floor_min: number;
  theta: number; combos: string; hours_window: string; pairs: string;
  hourly_guarantee: boolean; hourly_minute: number;
}

export interface AgentEventItem {
  ts?: string; kind: string; symbol?: string | null;
  summary: string; payload?: unknown;
}

export interface ResultsData {
  summary: {
    total: number; settled: number; open: number; wins: number; losses: number;
    draws: number; win_rate: number | null; est_pnl: number; dry_run: boolean;
  }
  by_symbol: Record<string, { trades: number; wins: number; losses: number;
                              win_rate: number | null }>
  trades: Trade[]
}

const API = ''

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(API + path)
  if (!r.ok) throw new Error(`${path}: ${r.status}`)
  return r.json()
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${path}: ${r.status}`)
  return r.json()
}

export async function put<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${path}: ${r.status}`)
  return r.json()
}
