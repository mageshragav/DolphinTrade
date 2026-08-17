"""Performance analytics: equity curve, streaks, heatmaps, per-group stats.

Used by the /api/analytics endpoint and the nightly Telegram report.
All functions are async and take a session; trade rows come from persistence.
"""

import logging
from datetime import datetime, timezone

import numpy as np

from app.services import persistence, risk

LOGGER = logging.getLogger('dolphin')

WIN_LOSS = ('WIN', 'LOSS')


def _settled(trades):
    return [t for t in trades if t.result in WIN_LOSS]


def _pnl(t) -> float:
    if t.result == 'WIN':
        return round((t.stake or 0.0) * (t.winperc or 0.0) / 100.0, 2)
    if t.result == 'LOSS':
        return -(t.stake or 0.0)
    return 0.0


def _streaks(settled, target: str) -> int:
    best = cur = 0
    for t in settled:
        if t.result == target:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


async def analytics(session, n: int = 500) -> dict:
    """Full performance picture over the last `n` trades."""
    trades = await persistence.last_trades(session, n=n)
    settled = _settled(trades)
    wins = sum(1 for t in settled if t.result == 'WIN')
    losses = sum(1 for t in settled if t.result == 'LOSS')
    draws = sum(1 for t in settled if t.result == 'DRAW')
    pnls = [_pnl(t) for t in settled]

    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    net = sum(pnls)

    # equity curve (chronological)
    ordered = sorted(settled, key=lambda t: t.ts or datetime.min.replace(tzinfo=timezone.utc))
    curve, cum = [], 0.0
    for t in ordered:
        cum += _pnl(t)
        curve.append({'ts': t.ts.isoformat() if t.ts else None,
                      'symbol': t.symbol, 'action': t.action,
                      'order_type': t.order_type, 'pnl': round(_pnl(t), 2),
                      'equity': round(cum, 2)})

    # drawdown from the equity curve
    peak = trough = 0.0
    max_dd = 0.0
    for p in [c['equity'] for c in curve]:
        peak = max(peak, p)
        max_dd = max(max_dd, peak - p)

    # rolling win rate (last 20 settled)
    roll_win = None
    if len(settled) >= 10:
        window = settled[:20]
        roll_win = round(sum(1 for t in window if t.result == 'WIN') / len(window), 4)

    def group(keyfn):
        out = {}
        for t in settled:
            k = keyfn(t)
            g = out.setdefault(k, {'trades': 0, 'wins': 0, 'losses': 0, 'net': 0.0})
            g['trades'] += 1
            g['wins'] += t.result == 'WIN'
            g['losses'] += t.result == 'LOSS'
            g['net'] = round(g['net'] + _pnl(t), 2)
        for k, g in out.items():
            g['win_rate'] = round(g['wins'] / g['trades'], 3) if g['trades'] else None
        return out

    by_hour = {}
    for t in settled:
        if t.ts is None:
            continue
        h = t.ts.replace(tzinfo=timezone.utc).hour if t.ts.tzinfo is None else t.ts.hour
        g = by_hour.setdefault(h, {'trades': 0, 'wins': 0, 'losses': 0})
        g['trades'] += 1
        g['wins'] += t.result == 'WIN'
        g['losses'] += t.result == 'LOSS'
    for k, g in by_hour.items():
        g['win_rate'] = round(g['wins'] / g['trades'], 3) if g['trades'] else None

    by_day = {}
    for t in settled:
        if t.ts is None:
            continue
        ts = t.ts.replace(tzinfo=timezone.utc) if t.ts.tzinfo is None else t.ts
        day = ts.strftime('%Y-%m-%d')
        g = by_day.setdefault(day, {'trades': 0, 'wins': 0, 'losses': 0, 'net': 0.0})
        g['trades'] += 1
        g['wins'] += t.result == 'WIN'
        g['losses'] += t.result == 'LOSS'
        g['net'] = round(g['net'] + _pnl(t), 2)
    for k, g in by_day.items():
        g['win_rate'] = round(g['wins'] / g['trades'], 3) if g['trades'] else None

    drift = await risk.circuit_breaker_status(session)
    benchmark = await risk.get_benchmark(session)

    return {
        'summary': {
            'total': len(trades), 'settled': len(settled), 'wins': wins,
            'losses': losses, 'draws': draws,
            'win_rate': round(wins / len(settled), 4) if settled else None,
            'profit_factor': round(gross_win / gross_loss, 3) if gross_loss else None,
            'net_pnl': round(net, 2), 'max_drawdown': round(max_dd, 2),
            'expectancy': round(net / len(settled), 4) if settled else 0.0,
            'avg_pnl': round(np.mean(pnls), 4) if pnls else 0.0,
            'longest_win_streak': _streaks(settled, 'WIN'),
            'longest_loss_streak': _streaks(settled, 'LOSS'),
            'rolling_win_rate': roll_win,
            'dry_run': all(t.dry_run for t in trades) if trades else True,
        },
        'equity_curve': curve,
        'by_symbol': group(lambda t: t.symbol),
        'by_order_type': group(lambda t: t.order_type or 'binary'),
        'by_hour': dict(sorted(by_hour.items())),
        'by_day': dict(sorted(by_day.items())),
        'drift': drift,
        'benchmark': benchmark,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def build_nightly_report(a: dict) -> str:
    """Plain-text Telegram report generated from analytics data."""
    s = a['summary']
    lines = [
        '📊 Daily performance report',
        '============================',
        f'Period: {a["generated_at"][:10]}',
        f'Trades: {s["settled"]} settled  |  Win rate: '
        f'{s["win_rate"] if s["win_rate"] is not None else "n/a"}',
        f'Profit factor: {s["profit_factor"] if s["profit_factor"] is not None else "n/a"}'
        f'  |  Net PnL: {s["net_pnl"]:+.2f}',
        f'Max drawdown: {s["max_drawdown"]}  |  Expectancy: {s["expectancy"]:+.4f}',
        f'Longest streaks: {s["longest_win_streak"]}W / '
        f'{s["longest_loss_streak"]}L',
    ]
    if s['rolling_win_rate'] is not None:
        lines.append(f'Rolling win rate (20): {s["rolling_win_rate"]}')
    dr = a.get('drift', {})
    if dr.get('win_rate') is not None:
        lines.append(f'Drift: live {dr["win_rate"]} vs benchmark '
                     f'{dr["projected"]} ({dr.get("status", "ok")})')
    best = sorted(a.get('by_symbol', {}).items(),
                  key=lambda kv: (kv[1].get('net', 0) if kv[1].get('net') is not None else 0),
                  reverse=True)[:3]
    if best:
        lines.append('Best symbols: ' + ', '.join(
            f'{k} ({v["net"]:+.2f})' for k, v in best if v['trades']))
    worst = sorted(a.get('by_symbol', {}).items(),
                   key=lambda kv: (kv[1].get('net', 0) if kv[1].get('net') is not None else 0))[:2]
    if worst:
        lines.append('Worst symbols: ' + ', '.join(
            f'{k} ({v["net"]:+.2f})' for k, v in worst if v['trades']))
    return '\n'.join(lines)