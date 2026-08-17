"""Walk-forward backtest engine.

Replays archived candles through the SAME production decision path
(ml_service.decide_all feature/ML + risk gates + execution simulation) and
returns a trade log, equity curve and per-group stats.

No broker is contacted: binary legs settle on the close at expiry, multiplier
legs settle on SL/TP touch (conservative: stop-loss checked first within a
bar) or the close at the signal horizon.

Performance: features are computed ONCE per (symbol, bar_sec) over the full
history (the model only reads the last completed bar, and all indicators are
backward-looking - the MQL set is explicitly lookahead-tested), so a replay
over thousands of bars is near-instant.

Limitations (documented): the live news veto is not reproduced (the broker's
calendar feed only covers the current week, so historical vetoes are
unavailable); pass use_calendar_veto=False. Staking is flat stake_pct (loss-
streak reduction and tiered targets are production-time risk layers).
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

LOGGER = logging.getLogger('dolphin')

SLIPPAGE_TAX = 0.02
DEFAULT_PAYOUT = 0.90
MAX_MULTI_PNL_MULT = 200.0    # cap a multiplier leg's pnl at stake*200


# ---------------------------------------------------------------------------
# result aggregation helpers
# ---------------------------------------------------------------------------

def _pnl(t: dict) -> float:
    return t.get('pnl', 0.0)


def _summarize(trades: list[dict]) -> dict:
    settled = [t for t in trades if t.get('result') in ('WIN', 'LOSS', 'DRAW')]
    wins = sum(1 for t in settled if t['result'] == 'WIN')
    losses = sum(1 for t in settled if t['result'] == 'LOSS')
    draws = sum(1 for t in settled if t['result'] == 'DRAW')
    pnls = [_pnl(t) for t in settled]
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    net = sum(pnls)
    peak = trough = 0.0
    max_dd = 0.0
    cum = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    win_rate = wins / len(settled) if settled else None
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None
    expectancy = net / len(settled) if settled else 0.0
    sd = float(np.std(pnls)) if len(pnls) > 1 else 0.0
    return {
        'trades': len(trades),
        'settled': len(settled),
        'wins': wins, 'losses': losses, 'draws': draws,
        'win_rate': round(win_rate, 4) if win_rate is not None else None,
        'profit_factor': round(profit_factor, 3) if profit_factor is not None else None,
        'net_pnl': round(net, 2),
        'max_drawdown': round(max_dd, 2),
        'expectancy': round(expectancy, 4),
        'sharpe': round((expectancy / sd) if sd else 0.0, 3),
        'longest_loss_streak': _longest_streak(settled, 'LOSS'),
        'longest_win_streak': _longest_streak(settled, 'WIN'),
    }


def _longest_streak(settled: list[dict], result: str) -> int:
    best = cur = 0
    for t in settled:
        if t.get('result') == result:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _equity_curve(trades: list[dict]) -> list[dict]:
    out, cum = [], 0.0
    for t in sorted(trades, key=lambda x: x.get('decision_ts') or ''):
        cum += _pnl(t)
        out.append({'ts': t.get('decision_ts'), 'symbol': t.get('symbol'),
                    'action': t.get('action'), 'order_type': t.get('order_type'),
                    'pnl': round(_pnl(t), 2), 'equity': round(cum, 2)})
    return out


# ---------------------------------------------------------------------------
# simulated execution
# ---------------------------------------------------------------------------

def _simulate_binary(entry: float, direction: str, expiry_dt, bars: pd.DataFrame,
                     payout: float) -> dict:
    """Binary leg: settle on the close at/after expiry (mirrors tracker.settle)."""
    horizon = bars[bars['datetime'] >= expiry_dt]
    if horizon.empty:
        return {'result': None, 'exit_price': None, 'pnl': 0.0}
    exit_p = float(horizon.iloc[0]['close'])
    if exit_p > entry:
        result = 'WIN' if direction == 'CALL' else 'LOSS'
    elif exit_p < entry:
        result = 'WIN' if direction == 'PUT' else 'LOSS'
    else:
        result = 'DRAW'
    pnl = round((payout - SLIPPAGE_TAX) * 100, 2) if result == 'WIN' else (
        -100.0 if result == 'LOSS' else 0.0)
    return {'result': result, 'exit_price': round(exit_p, 5), 'pnl': pnl}


def _simulate_multiplier(entry: float, direction: str, expiry_dt, bars: pd.DataFrame,
                         stop_loss, take_profit, multi: int, stake: float) -> dict:
    """Multiplier leg: SL/TP touch within the horizon (SL checked first in a
    bar - conservative), else settle on the close at the horizon."""
    if bars.empty:
        return {'result': None, 'exit_price': None, 'pnl': 0.0}
    sign = 1.0 if direction == 'CALL' else -1.0
    sl = float(stop_loss) if stop_loss else None
    tp = float(take_profit) if take_profit else None
    exit_p, reason = entry, 'horizon'
    for _, b in bars[bars['datetime'] <= expiry_dt].iterrows():
        high, low, close = float(b['high']), float(b['low']), float(b['close'])
        # stop-loss touch takes precedence within the same bar
        if sl is not None and ((sign > 0 and low <= sl) or (sign < 0 and high >= sl)):
            exit_p, reason = sl, 'sl'
            break
        if tp is not None and ((sign > 0 and high >= tp) or (sign < 0 and low <= tp)):
            exit_p, reason = tp, 'tp'
            break
    else:
        exit_p = float(bars[bars['datetime'] >= expiry_dt].iloc[0]['close']) \
            if not bars[bars['datetime'] >= expiry_dt].empty else entry
    ret = (exit_p / entry - 1.0) * sign * multi if entry else 0.0
    pnl = round(stake * ret, 2)
    pnl = max(-stake * MAX_MULTI_PNL_MULT, min(pnl, stake * MAX_MULTI_PNL_MULT))
    result = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'DRAW')
    return {'result': result, 'exit_price': round(exit_p, 5), 'pnl': pnl,
            'close_reason': reason}


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------

class BacktestEngine:
    def __init__(self, ml, instruments_payout=None, theta=0.65):
        self.ml = ml
        self._payout = instruments_payout or (lambda pair: DEFAULT_PAYOUT)
        self.theta = theta

    def _payout_for(self, symbol: str) -> float:
        try:
            p = self._payout(symbol.split(':')[-1])
            return p if p and p > 0 else DEFAULT_PAYOUT
        except Exception:
            return DEFAULT_PAYOUT

    def run(self, candles: pd.DataFrame, combos, order_types=('binary',),
            stake_pct=0.01, equity=1000.0, theta=None,
            start=None, end=None, cooldown_min=30, max_trades_per_day=14,
            max_daily_loss_pct=5.0) -> dict:
        """Replay the decision pipeline over `candles`.

        candles: normalized frame (symbol, datetime UTC-aware, OHLCV).
        Returns {trades, summary, equity_curve, by_symbol, by_combo}.
        """
        theta = theta or self.theta
        stake_pct = stake_pct if stake_pct is not None else 0.01
        equity = equity if equity is not None else 1000.0
        cooldown_min = cooldown_min if cooldown_min is not None else 30
        max_trades_per_day = max_trades_per_day if max_trades_per_day is not None else 14
        max_daily_loss_pct = max_daily_loss_pct if max_daily_loss_pct is not None else 5.0
        df = candles.copy()
        if df.empty:
            return {'trades': [], 'summary': _summarize([]), 'equity_curve': [],
                    'by_symbol': {}, 'by_combo': {}}
        df['datetime'] = pd.to_datetime(df['datetime'])
        # normalise to naive-UTC: the production ML service strips tzinfo in
        # _normalize, so all feature rows come back naive - keep everything on
        # the same (naive-UTC) clock to avoid pandas comparison errors
        if df['datetime'].dt.tz is not None:
            df['datetime'] = df['datetime'].dt.tz_convert('UTC').dt.tz_localize(None)

        # precompute per-(symbol, bar_sec) feature frames once
        # (feature row at time t only uses bars <= t, so full-frame rows are
        #  valid at every earlier boundary)
        feature_rows = {}       # (symbol, bar_sec) -> DataFrame(datetime, features, meta)
        bar_secs = sorted({b for b, _ in combos})
        for bar_sec in bar_secs:
            feats, meta = self.ml.compute_features(df, bar_sec)
            # per-row meta (close/atr at that bar), keyed by (symbol, datetime)
            meta_by_key = {}
            for _, mrow in meta.iterrows():
                meta_by_key[(str(mrow['symbol']), mrow['datetime'])] = mrow
            for symbol, grp in feats.groupby('symbol', sort=False):
                if len(grp) < 2:
                    continue
                rows = []
                for _, r in grp.iterrows():
                    d = dict(r)
                    m = meta_by_key.get((symbol, d['datetime']))
                    rows.append({'datetime': d['datetime'],
                                 'features': {k: v for k, v in d.items()
                                              if k not in ('symbol', 'datetime')},
                                 'meta': m})
                feature_rows[(symbol, bar_sec)] = pd.DataFrame(rows).sort_values('datetime')

        # per-symbol bar frames for settlement lookups (built once)
        sym_bars = {}
        for sym, g in df.groupby('symbol', sort=False):
            g = g.sort_values('datetime')
            sym_bars[sym] = (g, g['datetime'].values)

        # batch-predict every (symbol, bar_sec, expiry) combination once, then
        # walk the time-ordered events using the cached probabilities
        expiries_by_bar = {b: sorted({e for bb, e in combos if bb == b})
                           for b in bar_secs}
        predictions = {}        # (symbol, bar_sec, exp) -> dict(row_idx -> (p_call, p_put))
        for (symbol, bar_sec), fr in feature_rows.items():
            for exp_sec in expiries_by_bar[bar_sec]:
                bundle = self.ml.combo_models.get((bar_sec, exp_sec))
                if bundle is None:
                    continue
                cols = list(bundle['columns'])
                X = pd.DataFrame([{c: fr.iloc[i]['features'].get(c, 0.0)
                                   for c in cols} for i in range(len(fr) - 1)],
                                 columns=cols)
                X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
                P = bundle['model'].predict_proba(X)
                preds = predictions.setdefault((symbol, bar_sec, exp_sec), {})
                for i in range(len(X)):
                    p1, p2 = float(P[i, 1]), float(P[i, 2])
                    if not (np.isnan(p1) or np.isnan(p2)):
                        preds[i] = (p1, p2)

        # build the event list: each (symbol, bar_sec) row boundary is an
        # event whose signal row is the previous row (last completed bar)
        events = []
        for (symbol, bar_sec), fr in feature_rows.items():
            times = fr['datetime'].tolist()
            for i in range(1, len(times)):
                events.append((times[i], symbol, bar_sec, i - 1, fr))
        events.sort(key=lambda e: e[0])

        trades = []
        last_trade_ts = {}        # symbol -> decision ts (cooldown)
        day_counts = {}           # YYYYMMDD -> trades placed
        day_losses = {}           # YYYYMMDD -> stakes lost

        for t, symbol, bar_sec, row_idx, fr in events:
            if start and t < pd.Timestamp(start).tz_localize(None):
                continue
            if end and t >= pd.Timestamp(end).tz_localize(None):
                continue
            row = fr.iloc[row_idx]
            for exp_sec in expiries_by_bar[bar_sec]:
                pred = predictions.get((symbol, bar_sec, exp_sec), {}).get(row_idx)
                if pred is None:
                    continue
                p_call, p_put = pred
                best = max(p_call, p_put)
                direction = 'CALL' if p_call >= p_put else 'PUT'
                payout = self._payout_for(symbol)
                ev = best * (payout - SLIPPAGE_TAX) - (1 - best)
                if not (best >= theta and ev > 0.0):
                    continue
                # risk gates (simulated, in-memory)
                day = t.strftime('%Y%m%d')
                if day_counts.get(day, 0) >= max_trades_per_day:
                    continue
                if day_losses.get(day, 0) >= equity * max_daily_loss_pct / 100.0:
                    continue
                if symbol in last_trade_ts and \
                        (t - last_trade_ts[symbol]) < timedelta(minutes=cooldown_min):
                    continue
                # entry from the signal bar (the last completed bar of this
                # bar_sec): its close, and expiry measured from ITS time
                m = row['meta']
                if m is None:
                    continue
                entry = float(m['close'])
                if not entry:
                    continue
                atr = float(m['atr14']) if not np.isnan(m['atr14']) else 0.0
                sign = 1.0 if direction == 'CALL' else -1.0
                tp = entry + sign * atr if atr else entry
                sl = entry - sign * 0.5 * atr if atr else entry
                expiry_dt = row['datetime'] + pd.Timedelta(seconds=exp_sec)
                bars, _bar_times = sym_bars[symbol]
                for ot in order_types:
                    stake = round(equity * stake_pct, 2)
                    if ot == 'binary':
                        sim = _simulate_binary(entry, direction, expiry_dt,
                                               bars, payout)
                        winperc = payout * 100 if sim['result'] == 'WIN' else 0.0
                    else:
                        multi = 100
                        sim = _simulate_multiplier(entry, direction, expiry_dt,
                                                   bars, sl, tp, multi, stake)
                        winperc = sim['pnl'] / stake * 100 if stake else 0.0
                    trades.append({
                        'symbol': symbol, 'tf': f'{bar_sec // 60}m',
                        'expiry': f'{exp_sec // 60}m', 'action': direction,
                        'order_type': ot, 'entry': round(entry, 5),
                        'stop_loss': round(sl, 5), 'take_profit': round(tp, 5),
                        'decision_ts': str(row['datetime']), 'expiry_ts': str(expiry_dt),
                        'best_prob': round(best, 4), 'ev_score': round(ev, 4),
                        'stake': stake, 'winperc': round(winperc, 2),
                        'result': sim['result'], 'exit_price': sim.get('exit_price'),
                        'pnl': sim['pnl'],
                        'close_reason': sim.get('close_reason'),
                    })
                    day_counts[day] = day_counts.get(day, 0) + 1
                    if sim['result'] == 'LOSS':
                        day_losses[day] = day_losses.get(day, 0) + stake
                    last_trade_ts[symbol] = t

        def _group(trades_, keyfn):
            out = {}
            for t_ in trades_:
                k = keyfn(t_)
                out.setdefault(k, []).append(t_)
            return {k: _summarize(v) for k, v in out.items()}

        return {
            'trades': trades,
            'summary': _summarize(trades),
            'equity_curve': _equity_curve(trades),
            'by_symbol': _group(trades, lambda x: x['symbol']),
            'by_combo': _group(trades, lambda x: f"{x['tf']}->{x['expiry']}"),
            'order_types': list(order_types),
            'params': {'theta': theta, 'stake_pct': stake_pct, 'equity': equity,
                       'cooldown_min': cooldown_min,
                       'max_trades_per_day': max_trades_per_day,
                       'max_daily_loss_pct': max_daily_loss_pct,
                       'start': str(start) if start else None,
                       'end': str(end) if end else None},
        }


def run_backtest_sync(ml, candles, instruments_payout=None, **kwargs):
    """Sync entry point (used by the API via asyncio.to_thread)."""
    engine = BacktestEngine(ml, instruments_payout=instruments_payout)
    return engine.run(candles, **kwargs)