import { useEffect, useState } from 'react'
import type { MonitorStatus, Settings } from '../api'
import { post } from '../api'
import { Card, Empty } from '../components/ui'

export function SettingsPage({ settings, status, onSave, onRefresh }: {
  settings: Settings | null; status: MonitorStatus | null
  onSave: (b: Partial<Settings>) => void; onRefresh: () => void
}) {
  const [form, setForm] = useState<Partial<Settings>>({})
  const [token, setToken] = useState('')
  const [tokenMsg, setTokenMsg] = useState('')
  const [tokenBusy, setTokenBusy] = useState(false)
  const [refreshMsg, setRefreshMsg] = useState('')
  const [refreshBusy, setRefreshBusy] = useState(false)
  const [useAllPairs, setUseAllPairs] = useState(false)
  const [allAvailablePairs, setAllAvailablePairs] = useState<string[]>([])
  const [accounts, setAccounts] = useState<{ id: number; name: string; group: string;
    type: string; currency: string; balance: number }[] | null>(null)

  useEffect(() => {
    post<{ ok: boolean; accounts?: typeof accounts }>('/api/accounts').then(r => {
      if (r.ok && r.accounts) setAccounts(r.accounts)
    }).catch(() => { /* ignore */ })
    // Fetch all available pairs
    post<{ ok: boolean; ftt_all?: string[]; fx_all?: string[] }>('/api/pairs').then(r => {
      if (r.ok) {
        const all = [...(r.ftt_all || []), ...(r.fx_all || [])]
        setAllAvailablePairs(all)
      }
    }).catch(() => { /* ignore */ })
  }, [])

  useEffect(() => { if (settings) setForm(settings) }, [settings])
  const f = (k: keyof Settings) => ({
    value: String(form[k] ?? ''),
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm(fm => ({ ...fm, [k]: e.target.value })),
  })

  const pushToken = async () => {
    if (!token.trim()) return
    setTokenBusy(true); setTokenMsg('swapping...')
    try {
      const r = await post<{ ok: boolean; token_expires_at?: string | null; msg?: string }>(
        '/api/token', { access_token: token.trim() })
      setTokenMsg(r.ok ? `verified - valid until ${r.token_expires_at ?? '?'}` : (r.msg || 'failed'))
      setToken('')
      onRefresh()
    } catch (e) {
      setTokenMsg(`error: ${e}`)
    } finally {
      setTokenBusy(false)
    }
  }

  const refreshToken = async () => {
    setRefreshBusy(true); setRefreshMsg('refreshing...')
    try {
      const r = await post<{ ok: boolean; method?: string; msg?: string }>(
        '/api/token/refresh', {})
      if (r.ok) {
        setRefreshMsg(`✓ ${r.method === 'broker_renew' ? 'Renewed via broker' : 'Headless login triggered'} - ${r.msg}`)
      } else {
        setRefreshMsg(`✗ ${r.msg || 'refresh failed'}`)
      }
      onRefresh()
    } catch (e) {
      setRefreshMsg(`error: ${e}`)
    } finally {
      setRefreshBusy(false)
    }
  }

  return (
    <div className="grid">
      <div>
        <Card title="Trading configuration">
          {settings && <>
            <div className="cfg-row" style={{ alignItems: 'center' }}>
              <label>Order markets</label>
              <label className="chk"><input type="checkbox"
                checked={!!(settings.order_types || []).includes('binary')}
                onChange={e => {
                  const cur = new Set(settings.order_types || [])
                  e.target.checked ? cur.add('binary') : cur.delete('binary')
                  onSave({ order_types: [...cur] as any })
                }} /> Binary (fixed time)</label>
              <label className="chk"><input type="checkbox"
                checked={!!(settings.order_types || []).includes('multiplier')}
                onChange={e => {
                  const cur = new Set(settings.order_types || [])
                  e.target.checked ? cur.add('multiplier') : cur.delete('multiplier')
                  onSave({ order_types: [...cur] as any })
                }} /> Forex (multiplier)</label>
              <span className="hint" style={{ margin: 0 }}>each signal trades both enabled markets</span>
            </div>
            {(settings.order_types || []).includes('multiplier') && (
              <>
                <div className="cfg-row"><label>Multiplicator</label>
                  <input {...f('multiplicator')} style={{ width: 56 }} /></div>
                <div className="cfg-row"><label>SL/TP mode</label>
                  <select value={form.sl_tp_mode || 'signal_levels'}
                    onChange={e => setForm(fm => ({ ...fm, sl_tp_mode: e.target.value as any }))}>
                    <option value="signal_levels">Signal levels</option>
                    <option value="atr">ATR-scaled</option>
                  </select>
                  {(settings.sl_tp_mode === 'atr' && (settings.order_types || []).includes('multiplier')) && (
                    <span className="hint">SL {form.atr_sl_mult}x ATR · TP {form.atr_tp_mult}x ATR</span>)}
                </div>
                {(settings.sl_tp_mode === 'atr' && (settings.order_types || []).includes('multiplier')) && (
                  <>
                    <div className="cfg-row"><label>ATR SL mult</label><input {...f('atr_sl_mult')} style={{ width: 56 }} /></div>
                    <div className="cfg-row"><label>ATR TP mult</label><input {...f('atr_tp_mult')} style={{ width: 56 }} /></div>
                  </>
                )}
              </>
            )}
            <div className="cfg-row"><label>Trade mode</label>
              <select value={form.trade_mode || 'dry'}
                onChange={e => onSave({ trade_mode: e.target.value as any })}>
                <option value="dry">Dry (record only)</option>
                <option value="shadow">Shadow (paper ledger)</option>
                <option value="live">Live (real orders)</option>
              </select>
              <span className="hint" style={{ margin: 0 }}>
                {form.trade_mode === 'live' ? 'places real broker orders' :
                 form.trade_mode === 'shadow' ? 'settles a paper ledger from live candles' :
                 'records decisions, no broker'}</span>
            </div>
            <div className="cfg-row"><label>Dry run</label>
              <input type="checkbox" checked={!!form.dry_run}
                onChange={e => setForm(fm => ({ ...fm, dry_run: e.target.checked }))} /></div>
            <div className="cfg-row"><label>P gate</label><input {...f('theta')} style={{ width: 56 }} /></div>
            <div className="cfg-row"><label>Hourly guarantee</label>
              <input type="checkbox" checked={!!form.hourly_guarantee}
                onChange={e => setForm(fm => ({ ...fm, hourly_guarantee: e.target.checked }))} />
              <span className="hint">pick best candidate when an hour has no trade</span></div>
            <div className="cfg-row"><label>Hourly floor</label><input {...f('hourly_floor')} style={{ width: 56 }} />
              <span className="hint">primary tier for the hourly pick</span></div>
            <div className="cfg-row"><label>Fallback floor</label><input {...f('hourly_floor_min')} style={{ width: 56 }} />
              <span className="hint">second tier when nothing clears the primary</span></div>
            <div className="cfg-row"><label>Scan minute</label><input {...f('hourly_minute')} style={{ width: 56 }} />
              <span className="hint">UTC minute of the hourly scan</span></div>
            <div className="cfg-row"><label>Combos</label><input {...f('combos')} style={{ width: 210 }} /></div>
            <div className="cfg-row"><label>Hours (UTC)</label><input {...f('hours_window')} style={{ width: 56 }} /></div>
            <div className="cfg-row"><label>Pairs</label>
              <input {...f('pairs')} style={{ width: 230 }} disabled={useAllPairs} />
              <label className="chk"><input type="checkbox" checked={useAllPairs}
                onChange={e => {
                  setUseAllPairs(e.target.checked)
                  if (e.target.checked && allAvailablePairs.length) {
                    setForm(fm => ({ ...fm, pairs: allAvailablePairs.join(',') }))
                  }
                }} /> Use all</label></div>
          </>}
        </Card>

        <Card title="Risk limits">
          {settings && <>
            <div className="cfg-row"><label>Max trades/day</label><input {...f('max_trades_per_day')} style={{ width: 56 }} /></div>
            <div className="cfg-row"><label>Max daily loss %</label><input {...f('max_daily_loss_pct')} style={{ width: 56 }} /></div>
            <div className="cfg-row"><label>HW stop %</label>
              <input {...f('hw_stop_pct')} style={{ width: 56 }} />
              <span className="hint">0 = off; block below peak equity</span></div>
            <div className="cfg-row"><label>Profit target %</label>
              <input {...f('daily_profit_target_pct')} style={{ width: 56 }} />
              <span className="hint">0 = off; tiered by trade count</span></div>
            <div className="cfg-row"><label>Loss-streak cut</label>
              <input {...f('loss_streak_reduce_after')} style={{ width: 56 }} />x
              <input {...f('loss_streak_stake_factor')} style={{ width: 56 }} />
              <span className="hint">reduce after N losses, factor</span></div>
            <div className="cfg-row"><label>News blackout</label>
              <input {...f('news_blackout_min')} style={{ width: 56 }} />
              <span className="hint">0 = off; veto med+high news ±min</span></div>
            <div className="cfg-row"><label>Max concurrent</label>
              <input {...f('max_concurrent')} style={{ width: 56 }} />
              <span className="hint">0 = unlimited; simultaneous open trades</span></div>
            <div className="cfg-row"><label>In-flight stake %</label>
              <input {...f('max_stake_in_flight_pct')} style={{ width: 56 }} />
              <span className="hint">0 = off; total open-stake cap of equity</span></div>
            <div className="cfg-row"><label>Stake %</label><input {...f('stake_pct')} style={{ width: 56 }} /></div>
            <div className="cfg-row"><label>Equity</label><input {...f('equity')} style={{ width: 70 }} /></div>
          </>}
        </Card>
        <div className="cfg-actions">
          <button onClick={() => settings && onSave({
            dry_run: !!form.dry_run, trade_mode: (form.trade_mode || 'dry') as any,
            theta: Number(form.theta), combos: String(form.combos),
            hours_window: String(form.hours_window), pairs: String(form.pairs),
            max_trades_per_day: Number(form.max_trades_per_day),
            max_daily_loss_pct: Number(form.max_daily_loss_pct),
            stake_pct: Number(form.stake_pct), equity: Number(form.equity),
            symbol_cooldown_min: settings.symbol_cooldown_min,
            order_type: (settings.order_types || ['binary'])[0] as any,
            order_types: settings.order_types as any,
            multiplicator: Number(form.multiplicator) || 100,
            sl_tp_mode: settings.sl_tp_mode,
            atr_sl_mult: Number(form.atr_sl_mult) || 1.5,
            atr_tp_mult: Number(form.atr_tp_mult) || 3.0,
            hw_stop_pct: Number(form.hw_stop_pct) || 0,
            daily_profit_target_pct: Number(form.daily_profit_target_pct) || 0,
            loss_streak_reduce_after: Number(form.loss_streak_reduce_after) || 0,
            loss_streak_stake_factor: Number(form.loss_streak_stake_factor) || 0.5,
            news_blackout_min: Number(form.news_blackout_min) || 0,
            max_concurrent: Number(form.max_concurrent) || 0,
            max_stake_in_flight_pct: Number(form.max_stake_in_flight_pct) || 0,
            hourly_floor: Number(form.hourly_floor) || 0.58,
            hourly_floor_min: Number(form.hourly_floor_min) || 0.55,
            hourly_guarantee: !!form.hourly_guarantee,
            hourly_minute: Number(form.hourly_minute) || 55,
          })}>Save all</button>
        </div>
      </div>

      <div>
        <Card title="Olymp session token">
          <div className="ag"><span>Token valid</span>
            <span style={{ color: status?.token_ok === false ? 'var(--red)' : 'var(--green)' }}>
              {status?.token_ok === false ? 'EXPIRED' : status?.token_ok ? 'ok' : 'unknown'}</span></div>
          {status?.token_expires_at && (
            <div className="ag"><span>Expires</span>
              <span>{new Date(status.token_expires_at).toUTCString()}</span></div>
          )}
          <div className="hint">The access_token is a ~48h JWT. Paste a fresh one here to hot-swap
            without restarting (or send it via Telegram: /token &lt;jwt&gt;).</div>
          <div className="cfg-row" style={{ marginTop: 10, alignItems: 'flex-start' }}>
            <textarea value={token} onChange={e => setToken(e.target.value)}
              placeholder="access_token=..." rows={4}
              style={{ flex: 1, resize: 'vertical' }} />
          </div>
          <div className="cfg-row">
            <button onClick={pushToken} disabled={tokenBusy || !token.trim()}>
              {tokenBusy ? 'Swapping...' : 'Hot-swap token'}
            </button>
            <span className="hint" style={{ margin: 0 }}>{tokenMsg}</span>
          </div>
          <div className="hint" style={{ marginTop: 12 }}>Or auto-refresh your token using broker renewal (no captcha) or headless login:</div>
          <div className="cfg-row" style={{ marginTop: 8 }}>
            <button onClick={refreshToken} disabled={refreshBusy}
              style={{ background: 'var(--blue)', color: '#fff' }}>
              {refreshBusy ? '⏳ Refreshing...' : '🔄 Auto-Refresh Token'}
            </button>
            <span className="hint" style={{ margin: 0 }}>{refreshMsg}</span>
          </div>
        </Card>

        <Card title="System">
          <div className="ag"><span>Mode</span><span>{status?.dry_run ? 'DRY RUN' : 'LIVE'}</span></div>
          <div className="ag"><span>Kill switch</span><span>{status?.kill_switch ? 'ON' : 'off'}</span></div>
          <div className="ag"><span>Trades today</span><span>{status?.trades_today ?? '-'} / {status?.max_trades_per_day ?? '-'}</span></div>
          <div className="ag"><span>Losses today</span><span>{status?.losses_today ?? '-'}</span></div>
          <div className="ag"><span>Models loaded</span><span>{status?.model_count ?? '-'}</span></div>
          <div className="ag"><span>News events</span><span>{status?.news_events ?? '-'}</span></div>
          <div className="ag"><span>Equity</span><span>${status?.equity ?? '-'}</span></div>
          <div className="ag"><span>Stake</span><span>{(status?.stake_pct ?? 0) * 100}%</span></div>
        </Card>

        <Card title="Broker accounts" count={accounts?.length ?? 0}>
          {!accounts && <Empty text="Loading accounts..." />}
          {accounts?.map(a => (
            <div key={a.id} className="ag">
              <span>{a.name} <span className="chip" style={{ background: '#1b2530', color: 'var(--dim)' }}>
                {a.group}</span></span>
              <span><b>{a.currency} {a.balance.toFixed(2)}</b></span>
            </div>
          ))}
        </Card>

        <Card title="Presets">
          <div className="cfg-row">
            {(['conservative', 'balanced', 'aggressive'] as const).map(p => (
              <button key={p} style={{ padding: '4px 14px' }}
                onClick={() => {
                  const v = { conservative: { stake_pct: 0.005, max_trades_per_day: 6, theta: 0.70, max_concurrent: 1 },
                              balanced: { stake_pct: 0.01, max_trades_per_day: 10, theta: 0.65, max_concurrent: 2 },
                              aggressive: { stake_pct: 0.02, max_trades_per_day: 20, theta: 0.60, max_concurrent: 4 } }[p]
                  onSave(v)
                }}>{p}</button>
            ))}
            <span className="hint" style={{ margin: 0 }}>quick risk profile presets</span>
          </div>
        </Card>
      </div>
    </div>
  )
}
