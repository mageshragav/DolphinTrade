import { useMemo } from 'react'
import type { AgentsStatus, Decision, MonitorStatus, ResultsData, Trade } from '../api'
import { Card, Table, Stat } from '../components/ui'

const BUCKETS = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9]

export function Analyze({ decisions, trades, results, agents, status }: {
  decisions: Decision[]; trades: Trade[]
  results: ResultsData | null; agents: AgentsStatus | null
  status: MonitorStatus | null
}) {
  const bySymbol = useMemo(() => {
    const m = new Map<string, { wins: number; losses: number; n: number }>()
    for (const t of trades) {
      if (t.result !== 'WIN' && t.result !== 'LOSS') continue
      const e = m.get(t.symbol) || { wins: 0, losses: 0, n: 0 }
      if (t.result === 'WIN') e.wins++; else e.losses++
      e.n++
      m.set(t.symbol, e)
    }
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n)
  }, [trades])

  const byCombo = useMemo(() => {
    const m = new Map<string, { wins: number; n: number }>()
    for (const t of trades) {
      if (t.result !== 'WIN' && t.result !== 'LOSS') continue
      const k = `${t.tf} -> ${t.expiry}`
      const e = m.get(k) || { wins: 0, n: 0 }
      if (t.result === 'WIN') e.wins++
      e.n++
      m.set(k, e)
    }
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n)
  }, [trades])

  const thetaHist = useMemo(() => {
    const bins = BUCKETS.map((b, i) => ({
      label: `${b.toFixed(2)}-${(BUCKETS[i + 1] ?? 1).toFixed(2)}`,
      count: 0,
    }))
    for (const d of decisions) {
      const p = d.best_prob ?? 0
      for (let i = 0; i < BUCKETS.length; i++) {
        if (p >= BUCKETS[i] && (i === BUCKETS.length - 1 || p < BUCKETS[i + 1])) {
          bins[i].count++
          break
        }
      }
    }
    const max = Math.max(1, ...bins.map(b => b.count))
    return { bins, max }
  }, [decisions])

  const signals = decisions.filter(d => d.action === 'CALL' || d.action === 'PUT')
  const avgP = signals.length
    ? signals.reduce((s, d) => s + (d.best_prob ?? 0), 0) / signals.length : 0
  const cb = status?.circuit_breaker
  const wr = cb?.win_rate != null ? (cb.win_rate * 100).toFixed(1) + '%' : 'collecting'
  const s = results?.summary

  const hourly = useMemo(() => {
    // hours elapsed since the first trade/decision and hours with a trade
    const stamped = [...trades, ...decisions].map(d => d.ts).filter(Boolean) as string[]
    if (stamped.length === 0) return null
    const ts = stamped.map(t => new Date(t.replace(' ', 'T') + (t.includes('Z') || t.includes('+') ? '' : 'Z')))
    const first = Math.min(...ts.map(d => d.getTime()))
    const last = Math.max(...ts.map(d => d.getTime()))
    const hoursElapsed = Math.max(1, Math.ceil((last - first) / 3600000))
    const covered = new Set(trades
      .filter(t => t.status !== 'cancelled' && t.ts)
      .map(t => new Date(t.ts!.replace(' ', 'T') + 'Z').toISOString().slice(0, 13)))
    const fallback = trades.filter(t => (t.reason || '').includes('hourly')).length
    return { hoursElapsed, covered: covered.size, fallback }
  }, [trades, decisions])

  return (
    <div className="grid">
      <div>
        <Card title="Signal quality" count={signals.length}>
          <div className="stats">
            <Stat label="Signals (window)" value={signals.length} />
            <Stat label="Avg best P" value={avgP.toFixed(3)} color={avgP >= 0.65 ? 'var(--green)' : 'var(--amber)'} />
            <Stat label="P gate" value={status ? 'θ ' + (status.theta ?? 0.65).toFixed(2) : '--'} />
            <Stat label="EV estimate" value={s ? (s.win_rate != null
              ? (s.win_rate * 0.88 - (1 - s.win_rate)).toFixed(3) : '--') : '--'}
              color={s?.win_rate != null && s.win_rate * 0.88 > 1 - s.win_rate ? 'var(--green)' : 'var(--amber)'} />
          </div>
          <div className="hint">Probability distribution of recent decisions (θ threshold marks the trading gate):</div>
          <div className="hist">
            {thetaHist.bins.map((b, i) => (
              <div key={i} className="hist-bar" title={`${b.label}: ${b.count}`}>
                <div className="hist-fill"
                  style={{ height: `${(b.count / thetaHist.max) * 100}%` }} />
                <span>{b.label}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Win rate by symbol" count={bySymbol.length}>
          <Table cols={['Symbol', 'Trades', 'Wins', 'Losses', 'Win rate']}>
            {bySymbol.map(([sym, e]) => (
              <tr key={sym}>
                <td>{sym}</td><td>{e.n}</td><td className="a-CALL">{e.wins}</td>
                <td className="a-PUT">{e.losses}</td>
                <td style={{ color: e.wins / e.n >= 0.556 ? 'var(--green)' : 'var(--amber)', fontWeight: 700 }}>
                  {(e.wins / e.n * 100).toFixed(1)}%</td>
              </tr>
            ))}
            {bySymbol.length === 0 && <tr><td colSpan={5} className="empty">No settled trades yet</td></tr>}
          </Table>
        </Card>

        <Card title="Win rate by combo (TF -> expiry)" count={byCombo.length}>
          <Table cols={['Combo', 'Trades', 'Wins', 'Win rate']}>
            {byCombo.map(([k, e]) => (
              <tr key={k}>
                <td>{k}</td><td>{e.n}</td><td className="a-CALL">{e.wins}</td>
                <td style={{ color: e.wins / e.n >= 0.556 ? 'var(--green)' : 'var(--amber)', fontWeight: 700 }}>
                  {(e.wins / e.n * 100).toFixed(1)}%</td>
              </tr>
            ))}
            {byCombo.length === 0 && <tr><td colSpan={4} className="empty">No settled trades yet</td></tr>}
          </Table>
        </Card>
      </div>

      <div>
        <Card title="Circuit breaker" extra={cb?.paused ? <span className="pill kill">PAUSED</span> : undefined}>
          <div className="stats">
            <Stat label="Sample" value={cb?.sample ?? 0} />
            <Stat label="Live win rate" value={wr}
              color={cb?.win_rate != null && cb.win_rate >= 0.556 ? 'var(--green)' : 'var(--amber)'} />
            <Stat label="Projected" value={cb?.projected != null ? (cb.projected * 100).toFixed(0) + '%' : '--'} />
            <Stat label="Status" value={cb?.status ?? 'collecting'} />
          </div>
          <div className="hint">Pauses trading when realized win rate drifts more than 4pp below the projected edge for 50+ trades.</div>
        </Card>

        <Card title="Hourly coverage" count={hourly ? hourly.covered : 0}>
          {hourly ? (
            <>
              <div className="stats">
                <Stat label="Hours elapsed" value={hourly.hoursElapsed} />
                <Stat label="Hours with trade" value={hourly.covered} />
                <Stat label="Coverage"
                  value={(hourly.covered / hourly.hoursElapsed * 100).toFixed(0) + '%'}
                  color={hourly.covered / hourly.hoursElapsed >= 0.9 ? 'var(--green)' : 'var(--amber)'} />
                <Stat label="Hourly-pick trades" value={hourly.fallback} />
              </div>
              <div className="hint">Goal: ≥1 signal/trade per hour. Hours with a trade count as
                covered; the hourly-guarantee scan fills the rest with the best candidate
                above the floor (0.58).</div>
            </>
          ) : <div className="empty">No data yet - coverage appears once trades/decisions exist</div>}
        </Card>

        <Card title="Results summary">
          {s && <div className="stats">
            <Stat label="Total" value={s.total} />
            <Stat label="Settled" value={s.settled} />
            <Stat label="Win rate" value={s.win_rate != null ? (s.win_rate * 100).toFixed(1) + '%' : '--'}
              color={s.win_rate != null && s.win_rate >= 0.556 ? 'var(--green)' : 'var(--amber)'} />
            <Stat label="Est. P&L" value={<>{s.est_pnl >= 0 ? '+' : ''}{s.est_pnl.toFixed(2)}</>}
              color={s.est_pnl >= 0 ? 'var(--green)' : 'var(--red)'} />
          </div>}
        </Card>

        <Card title="Sentiment per pair">
          {agents && Object.entries(agents.sentiment).map(([p, sval]) => (
            <div key={p} className="ag"><span>{p}</span>
              <span className={`chip ${sval}`}>{sval}</span></div>
          ))}
          {(!agents || Object.keys(agents.sentiment).length === 0) &&
            <div className="empty">No sentiment data yet</div>}
        </Card>

        <Card title="Session">
          <div className="ag"><span>Token valid</span>
            <span style={{ color: status?.token_ok === false ? 'var(--red)' : 'var(--green)' }}>
              {status?.token_ok === false ? 'EXPIRED' : 'ok'}</span></div>
          {status?.token_expires_at && (
            <div className="ag"><span>Token expires</span><span>{new Date(status.token_expires_at).toUTCString()}</span></div>
          )}
        </Card>
      </div>
    </div>
  )
}
