import type { Decision, Trade } from './api'

// backend timestamps are naive UTC strings ('2026-08-14 07:31:08') -
// parse them as UTC explicitly so every display is correct
const parseTs = (s?: string) => {
  if (!s) return null
  const t = s.includes('Z') || s.includes('+') ? s : s.replace(' ', 'T') + 'Z'
  const d = new Date(t)
  return isNaN(d.getTime()) ? null : d
}
const fmtUTC = (d: Date | null) => (d ? d.toUTCString().slice(17, 25) : '-')
const fmtIST = (d: Date | null) => (d
  ? d.toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata', hour12: false,
      hour: '2-digit', minute: '2-digit' }) : '-')

export function timeCell(s?: string, dual = false) {
  return timeCellDate(parseTs(s), dual)
}

function timeCellDate(d: Date | null, dual = false) {
  if (!dual) return <td>{fmtUTC(d)}</td>
  return (
    <td title={`UTC ${fmtUTC(d)} · IST ${fmtIST(d)}`}>
      <span>UTC {fmtUTC(d)}</span>{' '}
      <span className="dim">IST {fmtIST(d)}</span>
    </td>
  )
}

const num = (v: number | null | undefined) => (v === null || v === undefined ? '-' : String(v))

export function decisionRow(d: Decision, dual = false) {
  const expMin = parseInt(d.expiry) || 15
  const base = parseTs(d.ts)
  const expTs = base ? new Date(base.getTime() + expMin * 60000) : null
  const sig = d.action === 'CALL' || d.action === 'PUT'
  const cls = d.action === 'CALL' ? 'a-CALL' : d.action === 'PUT' ? 'a-PUT' : 'a-NEUTRAL'
  return (
    <tr className={sig ? '' : 'dim'}>
      {timeCell(d.ts, dual)}<td>{d.symbol}</td><td>{d.tf}</td><td>{d.expiry}</td>
      <td className={cls}>{d.action === 'CALL' ? 'BUY' : d.action === 'PUT' ? 'SELL' : d.action}</td>
      <td>{d.best_prob?.toFixed(3)}</td>
      <td>{num(d.candle_open)}</td><td>{num(d.candle_close_price)}</td>
      <td>{num(d.entry_price)}</td><td>-</td>
      <td>{num(d.target_price)}</td><td>{num(d.stop_loss)}</td>
      <td>{timeCellDate(base ? new Date(base.getTime() + expMin * 60000) : null, dual)}</td>
      <td>-</td>
    </tr>
  )
}

export function tradeRow(t: Trade, dual = false, onSelect?: (t: Trade) => void) {
  const isBuy = t.action === 'CALL'
  const res = (t.result || '').toUpperCase()
  const resColor = res === 'WIN' ? 'var(--green)' : res === 'LOSS' ? 'var(--red)' : 'var(--dim)'
  return (
    <tr key={t.id} onClick={onSelect ? () => onSelect(t) : undefined}
      style={onSelect ? { cursor: 'pointer' } : undefined}>
      {timeCell(t.ts, dual)}<td>{t.symbol}</td><td>{t.tf}</td><td>{t.expiry}</td>
      <td className={isBuy ? 'a-CALL' : 'a-PUT'}>{isBuy ? 'BUY' : 'SELL'}</td><td>-</td>
      <td>{num(t.candle_open)}</td><td>{num(t.candle_close)}</td>
      <td>{num(t.entry)}</td><td>{num(t.exit_price)}</td>
      <td>{num(t.take_profit)}</td><td>{num(t.stop_loss)}</td>
      <td>{timeCell(t.expiry_time || undefined, dual)}</td>
      <td style={{ color: resColor, fontWeight: 700 }}>
        {t.result || (t.status === 'open' ? 'OPEN' : t.status)}
      </td>
    </tr>
  )
}

export const COLS = ['Time', 'Symbol', 'TF', 'Exp', 'Signal', 'P', 'Open', 'Close',
  'Entry', 'Exit', 'Take Profit', 'Stop Loss', 'Expiry Time', 'Result']

export const COLS_DUAL = ['Time (UTC · IST)', 'Symbol', 'TF', 'Exp', 'Signal', 'P', 'Open', 'Close',
  'Entry', 'Exit', 'Take Profit', 'Stop Loss', 'Expiry Time', 'Result']
