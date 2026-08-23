import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { LeadBadge, ScoreBar } from '../components/common'
import { api } from '../services/api'

const FILTERS = ['ALL', 'HOT', 'WARM', 'COLD', 'UNKNOWN']

export default function Leads() {
  const [params, setParams] = useSearchParams()
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const status = params.get('status') || 'ALL'

  useEffect(() => {
    setLoading(true)
    const query = new URLSearchParams()
    if (status !== 'ALL') query.set('status', status)
    if (search) query.set('search', search)
    query.set('limit', '200')

    const timer = setTimeout(() => {
      api
        .listLeads(`?${query.toString()}`)
        .then(setLeads)
        .catch(() => setLeads([]))
        .finally(() => setLoading(false))
    }, search ? 260 : 0)

    return () => clearTimeout(timer)
  }, [status, search])

  return (
    <div className="stack">
      <div className="card">
        <div className="between" style={{ marginBottom: 14 }}>
          <div className="row">
            {FILTERS.map((filter) => (
              <button
                key={filter}
                className={`btn-sm ${status === filter ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => {
                  const next = new URLSearchParams(params)
                  if (filter === 'ALL') next.delete('status')
                  else next.set('status', filter)
                  setParams(next)
                }}
              >
                {filter}
              </button>
            ))}
          </div>
          <div style={{ width: 260 }}>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search name or phone…"
            />
          </div>
        </div>

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Status</th>
                <th>Score</th>
                <th>Intent</th>
                <th>Budget</th>
                <th>Items</th>
                <th>Timeline</th>
                <th>Callback</th>
                <th>Last contact</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id} onClick={() => (window.location.href = `/leads/${lead.id}`)}>
                  <td>
                    <Link to={`/leads/${lead.id}`}>
                      <div style={{ fontWeight: 600 }}>{lead.customer_name || 'Unknown'}</div>
                      <div className="faint mono">{lead.phone_number}</div>
                    </Link>
                  </td>
                  <td>
                    <LeadBadge status={lead.status} />
                    {lead.do_not_call && (
                      <div className="faint" style={{ color: 'var(--danger)' }}>do-not-call</div>
                    )}
                  </td>
                  <td>
                    <div className="row">
                      <strong>{lead.score}</strong>
                      <ScoreBar score={lead.score} />
                    </div>
                  </td>
                  <td className="muted">
                    {lead.intent?.length ? lead.intent.map((i) => i.replace(/_/g, ' ')).join(', ') : '—'}
                  </td>
                  <td>{lead.budget ? `₹${lead.budget}` : '—'}</td>
                  <td className="muted">
                    {[...(lead.brands || []), ...(lead.clothing_categories || [])].join(', ') || '—'}
                  </td>
                  <td className="muted">{lead.timeline?.replace(/_/g, ' ') || '—'}</td>
                  <td className="muted">{lead.next_callback || '—'}</td>
                  <td className="faint">
                    {lead.last_interaction_at
                      ? new Date(lead.last_interaction_at).toLocaleDateString()
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!loading && leads.length === 0 && (
          <div className="center-empty">
            No leads yet. <Link to="/demo" style={{ color: 'var(--accent-bright)' }}>Run a demo call →</Link>
          </div>
        )}
        {loading && <div className="center-empty">Loading…</div>}
      </div>
    </div>
  )
}
