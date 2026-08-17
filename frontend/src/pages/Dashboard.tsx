import { Fragment, useEffect, useState } from 'react'
import type { AgentsStatus, ResultsData, Decision, Trade, SignalItem, MonitorStatus } from '../api'
import { decisionRow, tradeRow, COLS } from '../rows'
import { Card, Table, Empty, Stat } from '../components/ui'

export function Dashboard({ signals, neutrals, trades, results, agents, activity, log, nextCountdown, onSelectTrade, status, signalsSent }: {
  signals: Decision[]; neutrals: Decision[]; trades: Trade[]
  results: ResultsData | null; agents: AgentsStatus | null
  activity: string[]; log: string[]; nextCountdown: number | null
  onSelectTrade: (t: Trade) => void
  status: MonitorStatus | null; signalsSent: SignalItem[]
}) {
  return (
    <div className="grid">
      <div>
        <Card title="Live signals (CALL / PUT)" count={signals.length}>
          <Table cols={COLS}>
            {signals.length === 0 && <tr><td colSpan={14} className="empty">No signals yet</td></tr>}
            {signals.map((d, i) => <Fragment key={i}>{decisionRow(d)}</Fragment>)}
          </Table>
        </Card>
        <Card title="Neutral checks" count={neutrals.length}>
          <Table cols={COLS}>
            {neutrals.length === 0 && <tr><td colSpan={14} className="empty">No neutral checks yet</td></tr>}
            {neutrals.map((d, i) => <Fragment key={i}>{decisionRow(d)}</Fragment>)}
          </Table>
        </Card>
        <Card title="Trading signals (with results)" count={trades.length}>
          <Table cols={COLS}>
            {trades.length === 0 &&
              <tr><td colSpan={14} className="empty">No trades yet - signals will appear when the gate fires</td></tr>}
            {trades.map(t => tradeRow(t, false, onSelectTrade))}
          </Table>
        </Card>
        <ResultsCard data={results} />
      </div>
      <div>
        <AgentsCard agents={agents} nextCountdown={nextCountdown} />
        <ReadinessCard status={status} />
        <Card title="Telegram mirror" count={signalsSent.length}>
          {signalsSent.length === 0 && <Empty text="No signals forwarded to Telegram yet." />}
          <div className="scroll" style={{ maxHeight: 180 }}>
            {signalsSent.map(s => (
              <div key={s.id} className="ag">
                <span>{s.symbol} · {s.action} · {s.expiry}</span>
                <span className={`chip ${s.telegram_status === 'sent' ? 'ok' : ''}`}
                  style={s.telegram_status === 'sent'
                    ? { background: '#0e2a1c', color: 'var(--green)' }
                    : { background: '#1b2530', color: 'var(--dim)' }}>
                  {s.telegram_status || 'pending'}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Latest activity">
          {activity.map((a, i) => <div key={i} className="ag">{a}</div>)}
          {activity.length === 0 && <Empty text="waiting for agent events..." />}
        </Card>
        <Card title="Console">
          <details><summary>show raw log</summary>
            <pre>{log.join('\n')}</pre></details>
        </Card>
      </div>
    </div>
  )
}

export function ReadinessCard({ status }: { status: MonitorStatus | null }) {
  if (!status) return null
  const checks = [
    { label: 'Broker session token', ok: status.token_ok !== false },
    { label: 'Models loaded', ok: (status.model_count ?? 0) > 0 },
    { label: 'WebSocket connected', ok: status.running === true || status.running === false },
    { label: 'Scheduler running', ok: !!status.running },
    { label: 'Regime classified', ok: (status.regime ?? 'unknown') !== 'unknown' },
  ]
  const ready = checks.every(c => c.ok)
  return (
    <Card title="Readiness" extra={
      <span className={`chip ${ready ? 'ok' : ''}`}
        style={ready ? { background: '#0e2a1c', color: 'var(--green)' }
          : { background: '#2a1212', color: 'var(--red)' }}>
        {ready ? 'READY' : 'CHECK'}</span>}>
      {checks.map(c => (
        <div key={c.label} className="ag">
          <span>{c.label}</span>
          <span style={{ color: c.ok ? 'var(--green)' : 'var(--red)' }}>
            {c.ok ? '✓' : '✗'}</span>
        </div>
      ))}
    </Card>
  )
}

export function ResultsCard({ data }: { data: ResultsData | null }) {
  if (!data) return null
  const s = data.summary
  const wr = s.win_rate != null ? (s.win_rate * 100).toFixed(1) + '%' : '--'
  return (
    <Card title="Results tracking" count={s.settled}>
      <div className="stats">
        <Stat label="Wins" value={<span className="up">{s.wins}</span>} />
        <Stat label="Losses" value={<span className="dn">{s.losses}</span>} />
        <Stat label="Draws" value={s.draws} />
        <Stat label="Open" value={s.open} />
        <Stat label="Win rate" value={wr}
          color={s.win_rate != null && s.win_rate >= 0.556 ? 'var(--green)' : 'var(--amber)'} />
        <Stat label="Est. P&L"
          value={<>{s.est_pnl >= 0 ? '+' : ''}{s.est_pnl.toFixed(2)}</>}
          color={s.est_pnl >= 0 ? 'var(--green)' : 'var(--red)'} />
        <Stat label="Mode" value={s.dry_run ? 'dry-run' : 'live'} />
      </div>
      {data.trades.length > 0 && (
        <Table cols={['Symbol', 'Sig', 'Exp', 'Entry', 'Exit', 'Expiry time', 'Result', 'Mode']}
          maxHeight={260}>
          {data.trades.map(t => {
            const res = (t.result || '').toUpperCase()
            const color = res === 'WIN' ? 'var(--green)' : res === 'LOSS' ? 'var(--red)' : 'var(--dim)'
            return (
              <tr key={t.id}>
                <td>{t.symbol}</td>
                <td className={t.action === 'CALL' ? 'a-CALL' : 'a-PUT'}>{t.action === 'CALL' ? 'BUY' : 'SELL'}</td>
                <td>{t.expiry}</td><td>{t.entry}</td><td>{t.exit_price ?? '-'}</td>
                <td>{t.expiry_time ? new Date(t.expiry_time).toUTCString().slice(17, 25) : '-'}</td>
                <td style={{ color, fontWeight: 700 }}>{t.result || (t.status === 'open' ? 'OPEN' : t.status)}</td>
                <td>{t.dry_run ? 'sim' : 'live'}</td>
              </tr>
            )
          })}
        </Table>
      )}
      {data.trades.length === 0 && <Empty text="No trades yet - results appear here after signals fire and expire." />}
    </Card>
  )
}

export function AgentsCard({ agents, nextCountdown }: {
  agents: AgentsStatus | null; nextCountdown: number | null
}) {
  const [cd, setCd] = useState('--')
  useEffect(() => {
    if (!nextCountdown) return
    const t = setInterval(() => {
      const s = Math.max(0, Math.floor((nextCountdown - Date.now()) / 1000))
      setCd(`${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`)
      if (s <= 0) setCd('now')
    }, 1000)
    return () => clearInterval(t)
  }, [nextCountdown])
  return (
    <Card title="Market agents">
      <div className="ag"><span>News feed</span><span className="count">{agents?.news_events ?? '-'} events</span></div>
      <div className="ag"><span>Next high-impact</span><span>{agents?.next_event ?? '--'}</span></div>
      <div className="ag"><span>Countdown</span><span id="cd">{cd}</span></div>
      <div className="ag"><span>LLM sentiment</span><span>{agents?.llm ? 'gemini on' : 'lexicon'}</span></div>
      <div className="hint">Headline sentiment per pair:</div>
      {agents && Object.entries(agents.sentiment).map(([p, s]) => (
        <div key={p} className="ag"><span>{p}</span>
          <span className={`chip ${s}`}>{s}</span></div>
      ))}
    </Card>
  )
}
