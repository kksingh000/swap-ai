import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { LeadBadge, StatCard, useFetch } from '../components/common'
import { useEventStream } from '../hooks/useEventStream'
import { api } from '../services/api'

const ACTIVITY_ICON = { call: '📞', whatsapp: '💬', callback: '📅' }

export default function Dashboard({ events }) {
  const stats = useFetch(api.stats, [])
  const activity = useFetch(api.activity, [])
  const funnel = useFetch(api.funnel, [])
  const [hotLeads, setHotLeads] = useState([])

  useEffect(() => {
    api.listLeads('?status=HOT&limit=6').then(setHotLeads).catch(() => setHotLeads([]))
  }, [])

  // Any live event means the numbers on this page just went stale.
  useEventStream(events, (event) => {
    if (['call.ended', 'lead.updated', 'whatsapp.sent', 'action.completed'].includes(event.type)) {
      stats.reload()
      activity.reload()
      funnel.reload()
      api.listLeads('?status=HOT&limit=6').then(setHotLeads).catch(() => {})
    }
  })

  const s = stats.data || {}
  const maxFunnel = Math.max(1, ...(funnel.data?.stages || []).map((stage) => stage.value))

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Total calls" value={s.total_calls} icon="📞" />
        <StatCard label="Active calls" value={s.active_calls} icon="🔴" tone="accent" />
        <StatCard label="Hot leads" value={s.hot_leads} icon="🔥" tone="hot" />
        <StatCard label="Conversion rate" value={`${s.conversion_rate ?? 0}%`} icon="📈" tone="accent" />
      </div>

      <div className="grid grid-4">
        <StatCard label="Warm leads" value={s.warm_leads} icon="🌤️" tone="warm" />
        <StatCard label="Cold leads" value={s.cold_leads} icon="❄️" tone="cold" />
        <StatCard label="WhatsApp sent" value={s.whatsapp_sent} icon="💬" />
        <StatCard label="Callbacks scheduled" value={s.callbacks_scheduled} icon="📅" />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.35fr) minmax(0, 1fr)' }}>
        <div className="card">
          <div className="card-title">Lead funnel</div>
          {(funnel.data?.stages || []).map((stage) => (
            <div className="funnel-row" key={stage.label}>
              <div className="funnel-label">{stage.label}</div>
              <div className="funnel-track">
                <div className="funnel-fill" style={{ width: `${(stage.value / maxFunnel) * 100}%` }} />
              </div>
              <div className="funnel-value">{stage.value}</div>
            </div>
          ))}
          {!funnel.data?.stages?.length && <div className="center-empty">No calls yet.</div>}

          <div className="grid grid-3" style={{ marginTop: 20 }}>
            <div>
              <div className="faint">Avg lead score</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{s.avg_lead_score ?? 0}</div>
            </div>
            <div>
              <div className="faint">Avg call length</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{s.avg_call_duration_seconds ?? 0}s</div>
            </div>
            <div>
              <div className="faint">Do-not-call</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{s.do_not_call_count ?? 0}</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="between" style={{ marginBottom: 14 }}>
            <div className="card-title" style={{ margin: 0 }}>Hot leads</div>
            <Link to="/leads?status=HOT" className="faint">View all →</Link>
          </div>
          {hotLeads.length === 0 ? (
            <div className="center-empty">
              No hot leads yet.
              <br />
              <Link to="/demo" style={{ color: 'var(--accent-bright)' }}>Run a demo call →</Link>
            </div>
          ) : (
            hotLeads.map((lead) => (
              <Link to={`/leads/${lead.id}`} key={lead.id}>
                <div className="between" style={{ padding: '9px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{lead.customer_name || lead.phone_number}</div>
                    <div className="faint">
                      {lead.budget ? `₹${lead.budget}` : 'no budget'} ·{' '}
                      {lead.clothing_categories?.join(', ') || 'no items'}
                    </div>
                  </div>
                  <div className="row">
                    <strong>{lead.score}</strong>
                    <LeadBadge status={lead.status} />
                  </div>
                </div>
              </Link>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Recent activity</div>
        {(activity.data || []).length === 0 ? (
          <div className="center-empty">Nothing has happened yet.</div>
        ) : (
          (activity.data || []).map((item) => (
            <div className="action-item" key={`${item.kind}-${item.id}`}>
              <div className="action-icon">{ACTIVITY_ICON[item.kind] || '•'}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="between">
                  <strong style={{ fontSize: 13 }}>{item.title}</strong>
                  <span className="faint">{new Date(item.at).toLocaleString()}</span>
                </div>
                <div className="faint">
                  {item.detail} · {item.status}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
