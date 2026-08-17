export type Page = 'dashboard' | 'analyze' | 'settings' | 'list'

const ITEMS: { id: Page; label: string; icon: string; badge?: 'signals' | 'trades' }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '◈', badge: 'signals' },
  { id: 'analyze', label: 'Analyze', icon: '◔', badge: 'trades' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
  { id: 'list', label: 'List', icon: '☰' },
]

export function Sidebar({ page, onNav, signals, tradesToday }: {
  page: Page; onNav: (p: Page) => void; signals: number; tradesToday: number
}) {
  return (
    <nav className="sidebar">
      <div className="logo">🐬 DolphinTrade</div>
      <div className="side-items">
        {ITEMS.map(it => {
          const count = it.badge === 'signals' ? signals : it.badge === 'trades' ? tradesToday : 0
          return (
            <button key={it.id}
              className={`side-item${page === it.id ? ' active' : ''}`}
              onClick={() => onNav(it.id)}>
              <span className="ico">{it.icon}</span>
              <span>{it.label}</span>
              {count > 0 && <span className="badge">{count}</span>}
            </button>
          )
        })}
      </div>
      <div className="side-foot">multi-agent binary platform</div>
    </nav>
  )
}
