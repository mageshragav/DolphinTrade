import { Fragment, useEffect, useState } from 'react'
import { get, post, put, type AgentsStatus, type MonitorStatus, type Settings, type Trade, type Decision, type ResultsData, type AnalyticsData, type ShadowData } from './api'
import { useWebSocket, type WSMessage } from './ws'
import { Sidebar, type Page } from './components/Sidebar'
import { Dashboard } from './pages/Dashboard'
import { Analyze } from './pages/Analyze'
import { AnalyticsPage } from './pages/Analytics'
import { SettingsPage } from './pages/Settings'
import { ListPage } from './pages/List'

const PAGES: Page[] = ['dashboard', 'analyze', 'analytics', 'settings', 'list']

function pageFromHash(): Page {
  const h = location.hash.replace(/^#\/?/, '').split('?')[0].split('/')[0] as Page
  return PAGES.includes(h) ? h : 'dashboard'
}

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash)
  const [status, setStatus] = useState<MonitorStatus | null>(null)
  const [agents, setAgents] = useState<AgentsStatus | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [signals, setSignals] = useState<Decision[]>([])
  const [neutrals, setNeutrals] = useState<Decision[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [results, setResults] = useState<ResultsData | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [shadow, setShadow] = useState<ShadowData | null>(null)
  const [activity, setActivity] = useState<string[]>([])
  const [log, setLog] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')

  const refresh = async () => {
    try {
      const [st, ag, se, tr, de, rs, an, sh] = await Promise.all([
        get<MonitorStatus>('/api/monitor/status'),
        get<AgentsStatus>('/api/agents'),
        get<Settings>('/api/settings'),
        get<Trade[]>('/api/trades?n=30'),
        get<Decision[]>('/api/decisions?n=100'),
        get<ResultsData>('/api/results?n=200'),
        get<AnalyticsData>('/api/analytics'),
        get<ShadowData>('/api/analytics/shadow'),
      ])
      setStatus(st); setAgents(ag); setSettings(se); setTrades(tr); setResults(rs)
      setAnalytics(an); setShadow(sh)
      setSignals(de.filter(d => d.action === 'CALL' || d.action === 'PUT').slice(0, 40))
      setNeutrals(de.filter(d => d.action === 'NEUTRAL').slice(0, 40))
    } catch (e) { setError(String(e)) }
  }

  useEffect(() => { refresh(); const t = setInterval(refresh, 10000); return () => clearInterval(t) }, [])

  useEffect(() => {
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const nav = (p: Page) => { location.hash = `#/${p}`; setPage(p) }

  const onMsg = (m: WSMessage) => {
    if (m.type === 'status') { setStatus(s => s ? { ...s, running: m.running } : s); return }
    if (m.type === 'decision') {
      const d = m as unknown as Decision
      if (d.action === 'CALL' || d.action === 'PUT') {
        setSignals(s => [d, ...s.filter(x => x.symbol !== d.symbol ||
          x.candle_close !== d.candle_close)].slice(0, 40))
      } else {
        setNeutrals(s => [d, ...s.filter(x => x.symbol !== d.symbol ||
          x.candle_close !== d.candle_close)].slice(0, 40))
      }
      return
    }
    if (m.type === 'trade') { refresh(); return }
    if (m.type === 'trade_settled') { refresh(); return }
    if (m.type === 'agent') { setActivity(a => [m.line, ...a].slice(0, 12)); return }
    if (m.type === 'alert') { setActivity(a => [m.message, ...a].slice(0, 12)); return }
    if (m.type === 'log') { setLog(l => [...l.slice(-400), m.line]); return }
  }
  const wsConnected = useWebSocket(onMsg)
  useEffect(() => setConnected(wsConnected), [wsConnected])

  const control = async (action: string) => {
    await post('/api/monitor/control', { action })
    refresh()
  }
  const kill = async (on: boolean) => { await post('/api/monitor/kill', { on }); refresh() }
  const saveSettings = async (body: Partial<Settings>) => {
    await put('/api/settings', body); refresh()
  }

  const nextCountdown = agents?.next_event_time
    ? new Date(agents.next_event_time.replace(' ', 'T')).getTime() : null

  return (
    <div className="shell">
      <Sidebar page={page} onNav={nav}
        signals={signals.length} tradesToday={status?.trades_today ?? 0} />
      <div className="main">
        <div className="top">
          <span className={`pill ${status?.running ? 'run' : 'stop'}`}>
            {status?.running ? 'RUNNING' : 'STOPPED'}
          </span>
          <span className={`pill ${status?.kill_switch ? 'kill' : ''}`}>
            {status?.kill_switch ? 'KILL SWITCH' : status?.dry_run ? 'DRY RUN' : 'LIVE'}
          </span>
          {status?.regime && (
            <span className="pill" style={{ background: '#1b2530', color: 'var(--blue)', border: '1px solid var(--border)' }}>
              regime: {status.regime}
            </span>
          )}
          <span className="dot" style={{ background: connected ? 'var(--green)' : 'var(--red)' }}
            title={connected ? 'socket connected' : 'socket disconnected'} />
          <div className="meta">
            <div>Models: <b>{status?.model_count ?? '-'}</b> · News: <b>{status?.news_events ?? '-'}</b> · Trades today: <b>{status?.trades_today ?? '-'}</b></div>
            <div>Circuit breaker: <b style={{ color: status?.circuit_breaker.paused ? 'var(--red)' : 'var(--green)' }}>
              {status?.circuit_breaker.status ?? 'collecting'}</b>
              {status?.circuit_breaker.win_rate != null && ` (${(status.circuit_breaker.win_rate * 100).toFixed(0)}% vs proj ${(status.circuit_breaker.projected ?? 0) * 100}%)`}
            </div>
          </div>
          <button onClick={() => control('start')} disabled={status?.running}>▶ Start</button>
          <button className="stop" onClick={() => control('stop')} disabled={!status?.running}>■ Stop</button>
          <button className={status?.kill_switch ? 'stop' : ''}
            onClick={() => kill(!status?.kill_switch)}>{status?.kill_switch ? 'Resume' : 'Kill'}</button>
        </div>

        {error && <div className="err">{error}</div>}

        <div className="content">
          {page === 'dashboard' && (
            <Dashboard signals={signals} neutrals={neutrals} trades={trades}
              results={results} agents={agents} activity={activity} log={log}
              nextCountdown={nextCountdown} />
          )}
{page === 'analyze' && (
            <Analyze decisions={[...signals, ...neutrals]} trades={results?.trades ?? trades}
              results={results} agents={agents} status={status} />
          )}
          {page === 'analytics' && (
            <AnalyticsPage analytics={analytics} shadow={shadow} />
          )}
          {page === 'settings' && (
            <SettingsPage settings={settings} status={status}
              onSave={saveSettings} onRefresh={refresh} />
          )}
          {page === 'list' && <ListPage signals={signals} trades={trades} />}
        </div>
      </div>
    </div>
  )
}
