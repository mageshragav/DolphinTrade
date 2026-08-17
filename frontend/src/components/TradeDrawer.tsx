import { useEffect, useState } from 'react'
import type { Decision, Trade } from '../api'
import { get } from '../api'

interface Bar { datetime: string; open: number; high: number; low: number; close: number }

function MiniChart({ bars, entry }: { bars: Bar[]; entry: number | null | undefined }) {
  if (bars.length < 2) return null
  const W = 360, H = 120, PAD = 4
  const all = bars.flatMap(b => [b.high, b.low]).concat(entry ? [entry] : [])
  const min = Math.min(...all), max = Math.max(...all)
  const span = max - min || 1
  const step = (W - 2 * PAD) / bars.length
  const x = (i: number) => PAD + i * step + step / 2
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - 2 * PAD)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 120, display: 'block' }}>
      {bars.map((b, i) => {
        const up = b.close >= b.open
        const color = up ? 'var(--green)' : 'var(--red)'
        const cx = x(i)
        return (
          <g key={i}>
            <line x1={cx} y1={y(b.high)} x2={cx} y2={y(b.low)} stroke={color} strokeWidth="1" />
            <rect x={cx - 2} y={y(Math.max(b.open, b.close))} width={4}
              height={Math.max(1, y(Math.min(b.open, b.close)) - y(Math.max(b.open, b.close)))}
              fill={up ? color : 'var(--panel2)'} stroke={color} />
          </g>
        )
      })}
      {entry != null && <line x1={PAD} y1={y(entry)} x2={W - PAD} y2={y(entry)}
        stroke="var(--blue)" strokeDasharray="4 3" opacity="0.7" />}
    </svg>
  )
}

const fmt = (s?: string | null) => s ? new Date(s.replace(' ', 'T') + 'Z').toUTCString().slice(5, 25) : '-'

export function TradeDrawer({ trade, onClose }: { trade: Trade | null; onClose: () => void }) {
  const [decision, setDecision] = useState<Decision | null>(null)
  const [shadow, setShadow] = useState<Trade | null>(null)
  const [bars, setBars] = useState<Bar[]>([])

  useEffect(() => {
    setDecision(null); setShadow(null); setBars([])
    if (!trade) return
    const load = async () => {
      try {
        const ds = await get<Decision[]>('/api/decisions?n=200')
        const match = trade.decision_id
          ? ds.find(d => d.id === trade.decision_id)
          : ds.find(d => d.symbol === trade.symbol && d.action === trade.action &&
              (d.candle_close || '') === (trade.candle_close_ts || ''))
        setDecision(match ?? null)
      } catch { /* ignore */ }
      try {
        const ts = await get<Trade[]>('/api/trades?n=200')
        setShadow(ts.find(t => t.shadow && t.symbol === trade.symbol &&
          t.action === trade.action && t.expiry === trade.expiry &&
          t.candle_close_ts === trade.candle_close_ts) ?? null)
      } catch { /* ignore */ }
      try {
        const sym = trade.symbol.replace('FX:', '')
        const r = await get<{ ok: boolean; bars?: Bar[] }>(`/api/chart/${sym}?n=80`)
        if (r.ok && r.bars) setBars(r.bars)
      } catch { /* ignore */ }
    }
    load()
  }, [trade])

  if (!trade) return null
  const res = (trade.result || '').toUpperCase()
  const resColor = res === 'WIN' ? 'var(--green)' : res === 'LOSS' ? 'var(--red)' : 'var(--dim)'
  const isShadow = trade.shadow

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={e => e.stopPropagation()}>
        <div className="drawer-head">
          <h3>{trade.symbol} · {trade.action} · {trade.expiry}</h3>
          <button className="stop" style={{ padding: '4px 12px' }} onClick={onClose}>✕</button>
        </div>
        <div className="drawer-body">
          <div className="stats">
            <div className="stat"><span>Status</span>
              <b style={{ color: resColor }}>{trade.result || trade.status}</b></div>
            <div className="stat"><span>Entry</span><b>{trade.entry ?? '-'}</b></div>
            <div className="stat"><span>Exit</span><b>{trade.exit_price ?? '-'}</b></div>
            <div className="stat"><span>Stake</span><b>${trade.stake ?? 0}</b></div>
            {trade.winperc != null && <div className="stat"><span>Payout</span><b>{trade.winperc}%</b></div>}
            <div className="stat"><span>Mode</span><b>{isShadow ? 'shadow' : trade.dry_run ? 'dry' : 'live'}</b></div>
          </div>
          <div className="kv">
            <span>Entered</span><b>{fmt(trade.ts)}</b>
            <span>Expiry</span><b>{fmt(trade.expiry_time)}</b>
            <span>Take profit</span><b>{trade.take_profit ?? '-'}</b>
            <span>Stop loss</span><b>{trade.stop_loss ?? '-'}</b>
            {trade.broker_ref && <><span>Broker ref</span><b>{trade.broker_ref}</b></>}
            {trade.reason && <><span>Reason</span><b>{trade.reason}</b></>}
          </div>
          <div className="hint">Price action around entry (blue = entry level):</div>
          <MiniChart bars={bars} entry={trade.entry} />
          {decision && (
            <div className="drawer-section">
              <div className="hint">Model decision behind this trade</div>
              <div className="kv">
                <span>Model</span><b>{decision.model}</b>
                <span>P(CALL) / P(PUT)</span><b>{decision.p_call} / {decision.p_put}</b>
                <span>Best P / EV</span><b>{decision.best_prob} / {decision.ev_score}</b>
                <span>Sentiment</span><b>{decision.sentiment_bias}</b>
                <span>Manipulation risk</span><b>{decision.manipulation_risk}</b>
                <span>News veto</span><b>{decision.news_veto ? 'YES' : 'no'}</b>
                {decision.headline && <><span>Headline</span><b>{decision.headline}</b></>}
              </div>
              {decision.rationale && <div className="rationale">{decision.rationale}</div>}
            </div>
          )}
          {shadow && (
            <div className="drawer-section">
              <div className="hint">Shadow twin (paper ledger)</div>
              <div className="kv">
                <span>Result</span>
                <b style={{ color: (shadow.result || '').toUpperCase() === 'WIN' ? 'var(--green)' : 'var(--red)' }}>
                  {shadow.result || shadow.status}</b>
                <span>Exit</span><b>{shadow.exit_price ?? '-'}</b>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}