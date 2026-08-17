import { useEffect, useState } from 'react'
import type { AnalyticsData, BacktestResult, ShadowData } from '../api'
import { get, post } from '../api'
import { Card, Stat, Empty } from '../components/ui'

function EquityChart({ curve }: { curve: { equity: number }[] }) {
  if (curve.length < 2) {
    return <Empty text="Not enough settled trades for a curve yet." />
  }
  const W = 520, H = 140, PAD = 6
  const eq = curve.map(c => c.equity)
  const min = Math.min(0, ...eq), max = Math.max(0, ...eq)
  const span = max - min || 1
  const x = (i: number) => PAD + (i / (curve.length - 1)) * (W - 2 * PAD)
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - 2 * PAD)
  const pts = curve.map((c, i) => `${x(i).toFixed(1)},${y(c.equity).toFixed(1)}`).join(' ')
  const zero = y(0)
  const area = `${PAD},${zero} ${pts} ${x(curve.length - 1).toFixed(1)},${zero}`
  const last = eq[eq.length - 1]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="none">
      <line x1={PAD} y1={zero} x2={W - PAD} y2={zero}
        stroke="var(--dim)" strokeDasharray="3 3" />
      <polygon points={area} fill="var(--accent)" opacity="0.12" />
      <polyline points={pts} fill="none"
        stroke={last >= 0 ? 'var(--green)' : 'var(--red)'} strokeWidth="2" />
    </svg>
  )
}

function Heatmap({ byHour }: { byHour: Record<string, { trades: number; win_rate: number | null }> }) {
  const hours = Object.keys(byHour).map(Number).sort((a, b) => a - b)
  if (hours.length === 0) return <Empty text="No settled trades yet." />
  return (
    <div className="heat">
      {hours.map(h => {
        const g = byHour[h]
        const wr = g.win_rate
        const color = wr == null ? 'var(--dim)' : wr >= 0.6 ? 'var(--green)' : wr >= 0.45 ? 'var(--amber)' : 'var(--red)'
        return (
          <div key={h} className="cell" title={`${h}:00 UTC - ${g.trades} trades, ${wr != null ? (wr * 100).toFixed(0) + '%' : 'n/a'}`}
            style={{ background: color, opacity: wr == null ? 0.25 : 0.35 + 0.65 * (g.trades / 10) }}>
            {h}
          </div>
        )
      })}
    </div>
  )
}

function pct(v: number | null | undefined): string {
  return v == null ? '--' : (v * 100).toFixed(1) + '%'
}
function money(v: number): string {
  return (v >= 0 ? '+' : '') + v.toFixed(2)
}

function LedgerCard({ title, g }: { title: string; g: { trades: number; settled: number; win_rate: number | null; net_pnl: number } }) {
  return (
    <div className="ledger">
      <div className="ledger-title">{title}</div>
      <div className="ledger-row"><span>{g.trades} trades</span><span>{pct(g.win_rate)}</span></div>
      <div className="ledger-row"><span>Net PnL</span>
        <b style={{ color: g.net_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>{money(g.net_pnl)}</b></div>
    </div>
  )
}

export function AnalyticsPage({ analytics, shadow }: {
  analytics: AnalyticsData | null; shadow: ShadowData | null
}) {
  const [bt, setBt] = useState<{ theta: string; days: string; orderTypes: ('binary' | 'multiplier')[]; busy: boolean; result: BacktestResult | null; err: string }>({
    theta: '0.60', days: '5', orderTypes: ['binary'], busy: false, result: null, err: '',
  })

  const runBacktest = async () => {
    setBt(b => ({ ...b, busy: true, err: '', result: null }))
    try {
      const start = new Date()
      start.setUTCDate(start.getUTCDate() - Number(bt.days))
      const r = await post<BacktestResult>('/api/backtest/run', {
        theta: Number(bt.theta), order_types: bt.orderTypes,
        start: start.toISOString().slice(0, 10),
      })
      setBt(b => ({ ...b, busy: false, result: r }))
    } catch (e) {
      setBt(b => ({ ...b, busy: false, err: String(e) }))
    }
  }

  const s = analytics?.summary
  const drift = analytics?.drift
  const bench = analytics?.benchmark

  return (
    <div className="grid">
      <div>
        <Card title="Performance" count={s?.settled ?? 0}>
          {!analytics && <Empty text="Loading analytics..." />}
          {analytics && <>
            <div className="stats">
              <Stat label="Win rate" value={pct(s?.win_rate)}
                color={s && s.win_rate != null && s.win_rate >= (bench?.win_rate ?? 0.6) ? 'var(--green)' : 'var(--amber)'} />
              <Stat label="Profit factor" value={s?.profit_factor != null ? s.profit_factor.toFixed(2) : '--'} />
              <Stat label="Net PnL" value={<>{money(s?.net_pnl ?? 0)}</>}
                color={(s?.net_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'} />
              <Stat label="Max drawdown" value={s?.max_drawdown.toFixed(0)} />
              <Stat label="Expectancy" value={(s?.expectancy ?? 0).toFixed(3)} />
              <Stat label="Streaks" value={`${s?.longest_win_streak ?? 0}W / ${s?.longest_loss_streak ?? 0}L`} />
              {s?.rolling_win_rate != null &&
                <Stat label="Rolling WR (20)" value={pct(s.rolling_win_rate)} />}
            </div>
            <div className="chart-wrap">
              <EquityChart curve={analytics.equity_curve} />
            </div>
            <div className="hint">Equity curve (cumulative settled PnL)</div>
          </>}
        </Card>

        <Card title="Drift monitor" extra={drift && <span className={`chip ${drift.paused ? 'dn' : 'ok'}`}>{drift.status}</span>}>
          {drift && <>
            <div className="stats">
              <Stat label="Live WR" value={pct(drift.win_rate)} />
              <Stat label="Benchmark" value={pct(drift.projected)} />
              <Stat label="Sample" value={drift.sample} />
              {drift.drift_pts != null &&
                <Stat label="Drift" value={`${drift.drift_pts.toFixed(1)} pts`}
                  color={drift.drift_pts > 5 ? 'var(--red)' : 'var(--green)'} />}
            </div>
            <div className="hint">Benchmark comes from the last backtest (source: {bench?.source ?? 'default'}).
              Telegram alerts fire when live drops 5 pts below it.</div>
          </>}
        </Card>

        <Card title="Shadow vs Live (paper ledger)" count={(shadow?.shadow_count ?? 0) + (shadow?.live_count ?? 0)}>
          {shadow && <>
            <div className="ledger-row-wrap">
              <LedgerCard title="Shadow (paper)" g={shadow.shadow} />
              <LedgerCard title="Live" g={shadow.live} />
              <LedgerCard title="Dry-run" g={shadow.dry} />
            </div>
            <div className="hint">Shadow trades settle from live candles without touching the broker -
              the honest "what if" ledger to compare against live results.</div>
          </>}
        </Card>
      </div>

      <div>
        <Card title="Time-of-day win rate (UTC)">
          {analytics && <Heatmap byHour={analytics.by_hour} />}
        </Card>

        <Card title="Symbols" count={analytics ? Object.keys(analytics.by_symbol).length : 0}>
          {analytics && Object.entries(analytics.by_symbol).sort((a, b) => b[1].net - a[1].net).map(([sym, g]) => {
            const net = g.net
            const w = Math.min(100, Math.abs(net) * 4)
            return (
              <div key={sym} className="ag">
                <span>{sym}</span>
                <span className="bar-track">
                  <span className={`bar ${net >= 0 ? 'up' : 'dn'}`} style={{ width: w + '%' }} />
                </span>
                <span style={{ color: net >= 0 ? 'var(--green)' : 'var(--red)', width: 60, textAlign: 'right' }}>
                  {money(net)}</span>
              </div>
            )
          })}
        </Card>

        <Card title="Backtest replay" extra={bt.result && <span className="card-extra">saved as benchmark</span>}>
          <div className="cfg-row">
            <label>Theta</label>
            <input value={bt.theta} onChange={e => setBt(b => ({ ...b, theta: e.target.value }))} style={{ width: 56 }} />
            <label>Window</label>
            <select value={bt.days} onChange={e => setBt(b => ({ ...b, days: e.target.value }))}>
              <option value="3">3 days</option>
              <option value="5">5 days</option>
              <option value="7">7 days</option>
            </select>
            <label>Markets</label>
            <label className="chk"><input type="checkbox" checked={bt.orderTypes.includes('binary')}
              onChange={e => setBt(b => ({ ...b, orderTypes: e.target.checked
                ? [...b.orderTypes, 'binary'] : b.orderTypes.filter(x => x !== 'binary') }))} />Binary</label>
            <label className="chk"><input type="checkbox" checked={bt.orderTypes.includes('multiplier')}
              onChange={e => setBt(b => ({ ...b, orderTypes: e.target.checked
                ? [...b.orderTypes, 'multiplier'] : b.orderTypes.filter(x => x !== 'multiplier') }))} />Multiplier</label>
          </div>
          <div className="cfg-row">
            <button onClick={runBacktest} disabled={bt.busy || bt.orderTypes.length === 0}>
              {bt.busy ? 'Replaying...' : 'Run backtest'}
            </button>
            {bt.err && <span className="err" style={{ margin: 0 }}>{bt.err}</span>}
          </div>
          {bt.result && (() => {
            const r = bt.result
            return (
              <div className="stats">
                <Stat label="Trades" value={r.summary.trades} />
                <Stat label="Win rate" value={pct(r.summary.win_rate)}
                  color={r.summary.win_rate != null && r.summary.win_rate >= 0.6 ? 'var(--green)' : 'var(--amber)'} />
                <Stat label="Profit factor" value={r.summary.profit_factor != null ? r.summary.profit_factor.toFixed(2) : '--'} />
                <Stat label="Net PnL" value={<>{money(r.summary.net_pnl)}</>}
                  color={r.summary.net_pnl >= 0 ? 'var(--green)' : 'var(--red)'} />
                <Stat label="Max DD" value={r.summary.max_drawdown.toFixed(0)} />
                <Stat label="Sharpe" value={r.summary.sharpe.toFixed(2)} />
              </div>
            )
          })()}
          <div className="hint">Replays archived candles through the live ML pipeline (no broker).
            ≥20 settled trades auto-saves the result as the drift benchmark.</div>
        </Card>
      </div>
    </div>
  )
}