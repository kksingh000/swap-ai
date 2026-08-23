import { useEffect, useState } from 'react'

import { LeadBadge, useFetch } from '../components/common'
import { api } from '../services/api'

export default function Calls() {
  const { data: calls } = useFetch(() => api.listCalls('?limit=100'), [])
  const [selected, setSelected] = useState(null)
  const [transcript, setTranscript] = useState(null)

  useEffect(() => {
    if (!selected) return setTranscript(null)
    api.transcript(selected).then(setTranscript).catch(() => setTranscript(null))
  }, [selected])

  return (
    <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.3fr) minmax(0, 1fr)' }}>
      <div className="card">
        <div className="card-title">Calls</div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Turns</th>
                <th>Result</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {(calls || []).map((call) => (
                <tr
                  key={call.id}
                  onClick={() => setSelected(call.id)}
                  style={selected === call.id ? { background: 'var(--bg-hover)' } : undefined}
                >
                  <td className="mono">{call.id}</td>
                  <td>
                    <span className="chip">{call.mode === 'phone' ? '📞 phone' : '🎙️ demo'}</span>
                  </td>
                  <td className="muted">{call.status}</td>
                  <td>{call.turn_count}</td>
                  <td>
                    <div className="row">
                      <strong>{call.final_score}</strong>
                      <LeadBadge status={call.final_status} />
                    </div>
                  </td>
                  <td className="faint">{new Date(call.started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!calls?.length && <div className="center-empty">No calls recorded yet.</div>}
      </div>

      <div className="card">
        <div className="card-title">Transcript</div>
        {!transcript ? (
          <div className="center-empty">Select a call to read its transcript.</div>
        ) : (
          <>
            {transcript.summary && (
              <div className="banner" style={{ marginBottom: 14 }}>
                <span>📝</span>
                <div>{transcript.summary}</div>
              </div>
            )}
            <div className="transcript" style={{ maxHeight: 520 }}>
              {transcript.turns.map((turn, index) => (
                <div
                  key={index}
                  className={`bubble ${turn.role === 'agent' ? 'bubble-agent' : 'bubble-customer'}`}
                >
                  <div className="bubble-body">{turn.content}</div>
                  <div className="bubble-meta">
                    {turn.role === 'agent' ? '🤖 Ananya' : '👤 Customer'}
                    {turn.intent ? ` · ${turn.intent}` : ''}
                    {turn.score_after != null ? ` · score ${turn.score_after}` : ''}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
