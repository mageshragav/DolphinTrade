import { useEffect, useState } from 'react'
import type { AgentEventItem } from '../api'
import { get } from '../api'
import { Card, Empty } from '../components/ui'

const KIND_COLOR: Record<string, string> = {
  news: 'var(--blue)', sentiment: 'var(--blue)', risk: 'var(--amber)',
  drift: 'var(--red)', system: 'var(--dim)', report: 'var(--green)',
}

function kindIcon(kind: string): string {
  return { drift: '⚠', system: '⚙', news: '📰', sentiment: '💬',
           risk: '🛡', report: '📊' }[kind] || '•'
}

export function AlertsPage() {
  const [events, setEvents] = useState<AgentEventItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        setEvents(await get<AgentEventItem[]>('/api/agent-events?n=100'))
      } catch { /* ignore */ } finally { setLoading(false) }
    }
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [])

  const driftEvents = events.filter(e => e.kind === 'drift')
  const otherEvents = events.filter(e => e.kind !== 'drift')

  const renderRow = (e: AgentEventItem, i: number) => {
    const payload = e.payload as Record<string, unknown> | undefined
    return (
      <div key={i} className="ag" style={{ alignItems: 'flex-start' }}>
        <span>{kindIcon(e.kind)}</span>
        <span style={{ flex: 1 }}>
          <b>{e.summary}</b>
          {payload && Object.keys(payload).length > 0 &&
            <div className="hint" style={{ margin: 0 }}>
              {JSON.stringify(payload).slice(0, 240)}</div>}
        </span>
        <span style={{ color: 'var(--dim)', fontSize: 11 }}>
          {e.ts ? new Date(e.ts.replace(' ', 'T')).toUTCString().slice(17, 25) : ''}</span>
      </div>
    )
  }

  return (
    <div className="grid">
      <div>
        <Card title="Drift & risk alerts" count={driftEvents.length} extra={
          <span className="chip" style={{ background: '#0e2a1c', color: 'var(--green)' }}>
            auto-monitored</span>}>
          {loading && <Empty text="Loading..." />}
          {!loading && driftEvents.length === 0 &&
            <Empty text="No drift alerts. The monitor compares live win rate vs the backtest benchmark hourly." />}
          {driftEvents.map(renderRow)}
        </Card>
      </div>
      <div>
        <Card title="Agent activity" count={otherEvents.length}>
          {!loading && otherEvents.length === 0 &&
            <Empty text="No agent events yet (news refreshes, regime flips, retrains...)." />}
          {otherEvents.map(renderRow)}
        </Card>
      </div>
    </div>
  )
}