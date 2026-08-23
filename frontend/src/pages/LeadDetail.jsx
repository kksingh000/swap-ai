import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ActionFeed, KeyValues, LeadBadge, Reasons, ScoreGauge, useToasts } from '../components/common'
import { api } from '../services/api'

const TABS = ['Transcript', 'Scoring', 'Actions', 'WhatsApp', 'Callbacks']

export default function LeadDetail() {
  const { id } = useParams()
  const [lead, setLead] = useState(null)
  const [tab, setTab] = useState('Transcript')
  const [busy, setBusy] = useState(false)
  const { push, host } = useToasts()

  const load = () => api.getLead(id).then(setLead).catch(() => setLead(null))

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (!lead) return <div className="center-empty">Loading lead…</div>

  const memory = lead.memory || {}
  const latestScore = lead.score_history?.[lead.score_history.length - 1]

  async function sendFollowUp() {
    setBusy(true)
    try {
      const result = await api.sendWhatsApp({ lead_id: lead.id, use_template: true })
      push(`WhatsApp ${result.status} (${result.template_kind})`, 'success')
      await load()
      setTab('WhatsApp')
    } catch (error) {
      push(error.message, 'warn')
    } finally {
      setBusy(false)
    }
  }

  async function toggleDoNotCall() {
    setBusy(true)
    try {
      await api.patchLead(lead.id, { do_not_call: !lead.do_not_call })
      push(lead.do_not_call ? 'Removed from do-not-call' : 'Marked do-not-call', 'success')
      await load()
    } catch (error) {
      push(error.message, 'warn')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      {host}

      <div className="card">
        <div className="between">
          <div>
            <div className="row">
              <h2 style={{ fontSize: 20 }}>{lead.customer_name || 'Unknown customer'}</h2>
              <LeadBadge status={lead.status} />
              {lead.do_not_call && <span className="chip" style={{ color: 'var(--danger)' }}>do-not-call</span>}
            </div>
            <div className="faint mono" style={{ marginTop: 3 }}>
              {lead.phone_number} · lead #{lead.id} · {lead.language}
            </div>
          </div>
          <div className="row">
            <button onClick={sendFollowUp} disabled={busy || lead.do_not_call}>
              💬 Send follow-up
            </button>
            <button className={lead.do_not_call ? '' : 'btn-danger'} onClick={toggleDoNotCall} disabled={busy}>
              {lead.do_not_call ? 'Allow calls' : '🚫 Do not call'}
            </button>
            <Link to="/leads"><button className="btn-ghost">← Back</button></Link>
          </div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.6fr)' }}>
        <div className="stack">
          <div className="card">
            <div className="card-title">Lead score</div>
            <ScoreGauge score={lead.score} status={lead.status} />
          </div>

          <div className="card">
            <div className="card-title">What we know</div>
            <KeyValues
              items={[
                ['Intent', memory.intent],
                ['Budget', lead.budget ? `₹${lead.budget}` : null],
                ['Items', lead.clothing_categories],
                ['Brands', lead.brands],
                ['Size', lead.size],
                ['Timeline', lead.timeline?.replace(/_/g, ' ')],
                ['Location', lead.location],
                ['Barriers', lead.barriers?.map((b) => b.replace(/_/g, ' '))],
                ['Sentiment', lead.sentiment],
                ['Next callback', lead.next_callback],
              ]}
            />
          </div>
        </div>

        <div className="card">
          <div className="tabs">
            {TABS.map((item) => (
              <button
                key={item}
                className={`tab ${tab === item ? 'active' : ''}`}
                onClick={() => setTab(item)}
              >
                {item}
              </button>
            ))}
          </div>

          {tab === 'Transcript' && (
            <div className="transcript" style={{ maxHeight: 520 }}>
              {lead.transcript?.length ? (
                lead.transcript.map((message) => (
                  <div
                    key={message.id}
                    className={`bubble ${message.role === 'agent' ? 'bubble-agent' : 'bubble-customer'}`}
                  >
                    <div className="bubble-body">{message.content}</div>
                    <div className="bubble-meta">
                      {message.role === 'agent' ? '🤖 Ananya' : '👤 Customer'}
                      {message.intent ? ` · ${message.intent}` : ''}
                      {message.score_after != null ? ` · score ${message.score_after}` : ''}
                    </div>
                  </div>
                ))
              ) : (
                <div className="center-empty">No conversation recorded.</div>
              )}
            </div>
          )}

          {tab === 'Scoring' && (
            <div className="stack">
              <div>
                <div className="card-title">Why this score</div>
                <Reasons reasons={lead.score_reasons} />
              </div>

              {latestScore && (
                <div>
                  <div className="card-title">Ensemble breakdown</div>
                  <div className="grid grid-3">
                    <div className="card" style={{ background: 'var(--bg)' }}>
                      <div className="faint">Rules engine</div>
                      <strong>{latestScore.rules_label || '—'}</strong>
                    </div>
                    <div className="card" style={{ background: 'var(--bg)' }}>
                      <div className="faint">Trained classifier</div>
                      <strong>
                        {latestScore.ml_label || 'not trained'}
                        {latestScore.ml_confidence
                          ? ` (${Math.round(latestScore.ml_confidence * 100)}%)`
                          : ''}
                      </strong>
                    </div>
                    <div className="card" style={{ background: 'var(--bg)' }}>
                      <div className="faint">LLM</div>
                      <strong>{latestScore.llm_label || 'not used'}</strong>
                    </div>
                  </div>
                  {latestScore.ensemble_detail?.votes && (
                    <div className="wrap" style={{ marginTop: 12 }}>
                      {Object.entries(latestScore.ensemble_detail.votes).map(([label, value]) => (
                        <span className="chip" key={label}>
                          {label}: {value}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div>
                <div className="card-title">Score over the conversation</div>
                <div className="row" style={{ gap: 6, alignItems: 'flex-end', height: 90 }}>
                  {(lead.score_history || []).map((entry) => (
                    <div
                      key={entry.id}
                      title={`${entry.score} · ${entry.classification}`}
                      style={{
                        width: 22,
                        height: `${Math.max(4, entry.score)}%`,
                        borderRadius: 4,
                        background:
                          entry.score >= 60
                            ? 'var(--hot)'
                            : entry.score >= 20
                              ? 'var(--warm)'
                              : 'var(--cold)',
                      }}
                    />
                  ))}
                  {!lead.score_history?.length && <div className="faint">No score history.</div>}
                </div>
              </div>
            </div>
          )}

          {tab === 'Actions' && <ActionFeed actions={lead.actions} />}

          {tab === 'WhatsApp' && (
            <div className="stack">
              {lead.whatsapp_messages?.length ? (
                lead.whatsapp_messages.map((message) => (
                  <div className="card" key={message.id} style={{ background: 'var(--bg)' }}>
                    <div className="between" style={{ marginBottom: 8 }}>
                      <span className={`badge badge-${message.template_kind || 'UNKNOWN'}`}>
                        {message.template_kind}
                      </span>
                      <span className="faint">
                        {message.status} · {message.provider} ·{' '}
                        {new Date(message.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{message.body}</div>
                  </div>
                ))
              ) : (
                <div className="center-empty">No WhatsApp messages sent.</div>
              )}
            </div>
          )}

          {tab === 'Callbacks' && (
            <div className="stack">
              {lead.callbacks?.length ? (
                lead.callbacks.map((callback) => (
                  <div className="card" key={callback.id} style={{ background: 'var(--bg)' }}>
                    <div className="between">
                      <strong>⏰ {callback.scheduled_time}</strong>
                      <span className="chip">{callback.status}</span>
                    </div>
                    <div className="faint" style={{ marginTop: 6 }}>
                      Heard: “{callback.original_text}”
                    </div>
                    <div className="faint">
                      Parsed as: {callback.interpretation} · confidence{' '}
                      {Math.round((callback.confidence || 0) * 100)}%
                    </div>
                  </div>
                ))
              ) : (
                <div className="center-empty">No callbacks scheduled.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
