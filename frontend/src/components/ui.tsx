import type { ReactNode } from 'react'

export function Card({ title, count, children, extra }: {
  title: string; count?: number; children: ReactNode; extra?: ReactNode
}) {
  return (
    <div className="card">
      <h2>{title} {count !== undefined && <span className="n">{count}</span>}
        {extra && <span className="card-extra">{extra}</span>}</h2>
      {children}
    </div>
  )
}

export function Table({ cols, children, maxHeight }: {
  cols: string[]; children: ReactNode; maxHeight?: number
}) {
  return (
    <div className="scroll" style={maxHeight ? { maxHeight } : undefined}>
      <table>
        <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>
}

export function Stat({ label, value, color }: {
  label: string; value: ReactNode; color?: string
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <b style={color ? { color } : undefined}>{value}</b>
    </div>
  )
}
