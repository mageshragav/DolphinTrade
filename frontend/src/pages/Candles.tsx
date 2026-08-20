import { useEffect, useMemo, useState } from 'react'
import { get } from '../api'
import { Card, Empty } from '../components/ui'

interface Bar { symbol: string; datetime: string; open: number; high: number;
                 low: number; close: number; volume: number }

const DEFAULT_PAIRS = ['EURUSD', 'USDJPY', 'GBPUSD', 'USDCAD', 'EURJPY', 'EURGBP', 'EURAUD', 'EURCAD']
const INTERVALS = [['300', '5m'], ['900', '15m'], ['1800', '30m'], ['3600', '1h']]

function CandleChart({ bars }: { bars: Bar[] }) {
  const W = 620, H = 260, PAD = 8, BW = 6
  const data = useMemo(() => {
    if (bars.length < 2) return null
    const all = bars.flatMap(b => [b.high, b.low])
    const min = Math.min(...all), max = Math.max(...all)
    const span = max - min || 1
    const step = (W - 2 * PAD) / bars.length
    const x = (i: number) => PAD + i * step + step / 2
    const y = (v: number) => H - PAD - ((v - min) / span) * (H - 2 * PAD)
    return { min, max, step, x, y, last: bars[bars.length - 1].close }
  }, [bars])
  if (!data) return <Empty text="Not enough bars yet." />
  const gridLines = [0.25, 0.5, 0.75].map(f => data.min + (data.max - data.min) * f)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="candles" preserveAspectRatio="none">
      {gridLines.map((v, i) => (
        <line key={i} x1={PAD} y1={data.y(v)} x2={W - PAD} y2={data.y(v)}
          stroke="var(--border)" strokeDasharray="2 3" />
      ))}
      <line x1={PAD} y1={data.y(data.last)} x2={W - PAD} y2={data.y(data.last)}
        stroke="var(--blue)" strokeDasharray="4 3" opacity="0.6" />
      {bars.map((b, i) => {
        const up = b.close >= b.open
        const color = up ? 'var(--green)' : 'var(--red)'
        const cx = data.x(i)
        const yTop = data.y(Math.max(b.open, b.close))
        const yBot = data.y(Math.min(b.open, b.close))
        const bodyH = Math.max(1.2, yBot - yTop)
        return (
          <g key={i}>
            <line x1={cx} y1={data.y(b.high)} x2={cx} y2={data.y(b.low)}
              stroke={color} strokeWidth="1" />
            <rect x={cx - BW / 2} y={yTop} width={BW} height={bodyH}
              fill={up ? color : 'var(--panel2)'} stroke={color} strokeWidth="1" />
          </g>
        )
      })}
    </svg>
  )
}

export function CandlesPage() {
  const [pair, setPair] = useState(DEFAULT_PAIRS[0])
  const [interval, setInterval] = useState('300')
  const [bars, setBars] = useState<Bar[]>([])
  const [pairs, setPairs] = useState<string[]>(DEFAULT_PAIRS)
  const [err, setErr] = useState('')

  const load = async () => {
    try {
      const r = await get<{ ok: boolean; bars?: Bar[]; msg?: string }>(
        `/api/chart/${pair}?n=120&interval=${interval}`)
      if (r.ok && r.bars) setBars(r.bars)
      else if (!r.ok) setErr(r.msg || 'no data')
    } catch (e) { setErr(String(e)) }
  }

  useEffect(() => {
    get<{ ok: boolean; ftt_currency?: string[]; ftt_all?: string[]; fx_all?: string[] }>('/api/pairs')
      .then(r => {
        if (r.ok) {
          const all = [...(r.ftt_all || r.ftt_currency || []), ...(r.fx_all || [])]
          if (all.length) setPairs(all)
        }
      })
      .catch(() => { /* keep defaults */ })
  }, [])

  useEffect(() => { load(); const t = window.setInterval(load, 5000); return () => window.clearInterval(t) }, [pair, interval])

  const last = bars[bars.length - 1]
  return (
    <div className="grid">
      <div>
        <Card title="Live candlestick chart" extra={
          <span className="card-extra">
            <select value={pair} onChange={e => setPair(e.target.value)}>
              {pairs.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={interval} onChange={e => setInterval(e.target.value)}>
              {INTERVALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </span>}>
          {err && <div className="hint">{err}</div>}
          <CandleChart bars={bars} />
          {last && (
            <div className="hint">
              {pair} · last bar {new Date(last.datetime).toUTCString().slice(5, 22)} ·
              O {last.open} H {last.high} L {last.low} C <b style={{ color: last.close >= last.open ? 'var(--green)' : 'var(--red)' }}>{last.close}</b>
            </div>
          )}
        </Card>
      </div>
      <div>
        <Card title="Recent bars" count={bars.length}>
          <div className="scroll" style={{ maxHeight: 300 }}>
            <table>
              <thead><tr><th>Time (UTC)</th><th>O</th><th>H</th><th>L</th><th>C</th></tr></thead>
              <tbody>
                {[...bars].reverse().slice(0, 30).map((b, i) => (
                  <tr key={i}>
                    <td>{new Date(b.datetime).toUTCString().slice(17, 25)}</td>
                    <td>{b.open}</td><td>{b.high}</td><td>{b.low}</td>
                    <td style={{ color: b.close >= b.open ? 'var(--green)' : 'var(--red)' }}>{b.close}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}