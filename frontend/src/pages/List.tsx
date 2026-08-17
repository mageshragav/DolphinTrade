import { Fragment, useEffect, useMemo, useState } from 'react'
import type { Decision, Trade } from '../api'
import { decisionRow, tradeRow, COLS_DUAL } from '../rows'
import { Card } from '../components/ui'

type Filter = 'all' | 'signals' | 'trades'

interface ComboNode { key: string; label: string; signals: Decision[]; trades: Trade[] }
interface SymbolNode { symbol: string; combos: ComboNode[] }

function fmtSym(s: string) { return s.replace(/^FX:/, '') }

export function ListPage({ signals, trades }: { signals: Decision[]; trades: Trade[] }) {
  const [filter, setFilter] = useState<Filter>('all')
  const [open, setOpen] = useState<Set<string>>(new Set())

  const tree = useMemo<SymbolNode[]>(() => {    const bySym = new Map<string, Map<string, ComboNode>>()
    const ensure = (symbol: string) => {
      let m = bySym.get(symbol)
      if (!m) { m = new Map(); bySym.set(symbol, m) }
      return m
    }
    for (const d of signals) {
      const key = `${d.tf}->${d.expiry}`
      const m = ensure(d.symbol)
      if (!m.has(key)) m.set(key, { key, label: `${d.tf} → ${d.expiry}`, signals: [], trades: [] })
      m.get(key)!.signals.push(d)
    }
    for (const t of trades) {
      const key = `${t.tf}->${t.expiry}`
      const m = ensure(t.symbol)
      if (!m.has(key)) m.set(key, { key, label: `${t.tf} → ${t.expiry}`, signals: [], trades: [] })
      m.get(key)!.trades.push(t)
    }
    const out: SymbolNode[] = []
    for (const [symbol, combos] of bySym) {
      out.push({ symbol, combos: [...combos.values()].sort((a, b) => a.key.localeCompare(b.key)) })
    }
    return out.sort((a, b) => a.symbol.localeCompare(b.symbol))
  }, [signals, trades])

  const total = useMemo(() => {
    let s = 0, t = 0
    for (const n of tree) for (const c of n.combos) { s += c.signals.length; t += c.trades.length }
    return { s, t }
  }, [tree])

  // '#/list?open=1' deep link expands the whole tree
  useEffect(() => {
    if (location.hash.includes('open') && tree.length && open.size === 0) {
      setOpen(new Set(tree.flatMap(n =>
        [n.symbol, ...n.combos.map(c => `${n.symbol}/${c.key}`)])))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree])

  const toggle = (key: string) => {
    setOpen(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }

  const showSignals = filter !== 'trades'
  const showTrades = filter !== 'signals'

  return (
    <div className="list-wrap">
      <Card title="Tree navigation — Symbol → Combo → entries"
        count={filter === 'trades' ? total.t : filter === 'signals' ? total.s : total.s + total.t}
        extra={
          <div className="filter-tabs">
            {(['all', 'signals', 'trades'] as Filter[]).map(f => (
              <button key={f} className={`tab${filter === f ? ' on' : ''}`}
                onClick={() => setFilter(f)}>{f}</button>
            ))}
          </div>
        }>
        {tree.length === 0 && <div className="empty">No data yet — signals and trades will appear here</div>}
        {tree.map(symNode => {
          const symCount = symNode.combos.reduce(
            (a, c) => a + (showSignals ? c.signals.length : 0) + (showTrades ? c.trades.length : 0), 0)
          const expanded = open.has(symNode.symbol)
          return (
            <div key={symNode.symbol} className="tree">
              <div className="trow t-sym" onClick={() => toggle(symNode.symbol)}>
                <span className={`caret${expanded ? ' open' : ''}`}>▸</span>
                <span className="t-label">{fmtSym(symNode.symbol)}</span>
                <span className="badge">{symCount}</span>
              </div>
              {expanded && symNode.combos.map(combo => {
                const cCount = (showSignals ? combo.signals.length : 0) + (showTrades ? combo.trades.length : 0)
                const cKey = `${symNode.symbol}/${combo.key}`
                const cOpen = open.has(cKey)
                return (
                  <div key={cKey} className="tree t-child">
                    <div className="trow t-combo" onClick={() => toggle(cKey)}>
                      <span className={`caret${cOpen ? ' open' : ''}`}>▸</span>
                      <span className="t-label">{combo.label}</span>
                      <span className="badge">{cCount}</span>
                    </div>
                    {cOpen && (
                      <div className="t-leaf">
                        {showSignals && combo.signals.length > 0 && (
                          <div className="t-table">
                            <div className="t-table-title">Signals <span className="n">{combo.signals.length}</span></div>
                            <div className="scroll">
                              <table>
                                <thead><tr>{COLS_DUAL.map(c => <th key={c}>{c}</th>)}</tr></thead>
                                <tbody>{combo.signals.slice(0, 50).map((d, i) =>
                                  <Fragment key={i}>{decisionRow(d, true)}</Fragment>)}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                        {showTrades && combo.trades.length > 0 && (
                          <div className="t-table">
                            <div className="t-table-title">Trades <span className="n">{combo.trades.length}</span></div>
                            <div className="scroll">
                              <table>
                                <thead><tr>{COLS_DUAL.map(c => <th key={c}>{c}</th>)}</tr></thead>
                                <tbody>{combo.trades.map(t => tradeRow(t, true))}</tbody>
                              </table>
                            </div>
                          </div>
                        )}
                        {cCount === 0 && <div className="empty">no entries</div>}
                      </div>
                    )}
                  </div>
                )
              })}
              {symCount === 0 && <div className="empty">no entries</div>}
            </div>
          )
        })}
      </Card>
    </div>
  )
}
