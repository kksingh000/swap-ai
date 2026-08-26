import { NavLink, useLocation } from 'react-router-dom'

import { apiBaseUrl } from '../services/api'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '📊', end: true },
  { to: '/demo', label: 'Live Call', icon: '🎙️' },
  { to: '/leads', label: 'Leads', icon: '👥' },
  { to: '/calls', label: 'Call History', icon: '📞' },
  { to: '/callbacks', label: 'Callbacks', icon: '📅' },
  { to: '/training', label: 'AI & Training', icon: '🧠' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

const TITLES = {
  '/': 'Dashboard',
  '/demo': 'Live Call',
  '/leads': 'Lead Management',
  '/calls': 'Call History',
  '/callbacks': 'Scheduled Callbacks',
  '/training': 'AI & Training',
  '/settings': 'Settings',
}

export default function Layout({ children, connected, health, healthError }) {
  const { pathname } = useLocation()
  const title = TITLES[pathname] || (pathname.startsWith('/leads/') ? 'Lead Detail' : 'SwapCircle')

  const llm = health?.components?.llm
  const providerLabel = llm?.available ? llm.provider : 'rule-based (no LLM)'

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">🎙️</div>
          <div>
            <div className="brand-name">SwapCircle</div>
            <div className="brand-sub">AI Voice Sales Agent</div>
          </div>
        </div>

        <nav className="nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="row" style={{ marginBottom: 6 }}>
            <span className={`dot ${connected ? 'dot-live' : 'dot-off'}`} />
            <span className="faint">{connected ? 'Live channel open' : 'Reconnecting…'}</span>
          </div>
          <div className="faint">AI: {providerLabel}</div>
          <div className="faint">{health?.cost_mode || 'FREE mode'}</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="page-title">{title}</div>
          <div className="row">
            {health ? (
              <>
                <span className="chip">{health.components?.telephony?.provider} telephony</span>
                <span className="chip">{health.components?.whatsapp?.provider} whatsapp</span>
              </>
            ) : (
              <span className="chip" style={{ color: 'var(--danger)' }}>backend unreachable</span>
            )}
          </div>
        </header>
        <div className="page-body">
          {healthError && (
            <div className="banner warn" style={{ marginBottom: 18 }}>
              <span>&#9888;</span>
              <div>
                <strong>Can&rsquo;t reach the backend.</strong> Every provider below will read as
                mock and no call can be placed.
                <div className="mono" style={{ marginTop: 6 }}>
                  API: {apiBaseUrl()}
                </div>
                <div className="mono">Error: {healthError}</div>
                <div style={{ marginTop: 6 }}>
                  Usual causes: <code>VITE_API_BASE</code> not set at build time (the URL above
                  would point at this site instead of the API), or the API&rsquo;s
                  <code> CORS_ORIGINS</code> not listing <code>{window.location.origin}</code>.
                </div>
              </div>
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  )
}
