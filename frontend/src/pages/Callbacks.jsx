import { useEffect, useState } from 'react'

import { useFetch, useToasts } from '../components/common'
import { api } from '../services/api'

export default function Callbacks({ lastEvent }) {
  const { data: callbacks, reload } = useFetch(() => api.callbacks('?limit=200'), [])
  const [phrase, setPhrase] = useState('call me tomorrow evening around 6')
  const [parsed, setParsed] = useState(null)
  const { push, host } = useToasts()

  useEffect(() => {
    if (lastEvent?.type === 'callback.due') {
      push(`⏰ Callback due: ${lastEvent.data.customer_name || lastEvent.data.phone_number}`, 'warn')
      reload()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  async function parse() {
    try {
      setParsed(await api.parseTime(phrase))
    } catch (error) {
      push(error.message, 'warn')
    }
  }

  async function updateStatus(id, status) {
    await api.updateCallback(id, status)
    reload()
  }

  return (
    <div className="stack">
      {host}

      <div className="card">
        <div className="card-title">Natural-language time parser</div>
        <div className="faint" style={{ marginBottom: 12 }}>
          Whatever the customer says on the call runs through this exact parser. Try “kal shaam 6 baje”,
          “next Monday”, “after 6”, “this weekend”, “in 2 hours”.
        </div>
        <div className="row">
          <input
            value={phrase}
            onChange={(event) => setPhrase(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && parse()}
          />
          <button className="btn-primary" onClick={parse}>Parse</button>
        </div>
        {parsed && (
          <div className="grid grid-4" style={{ marginTop: 14 }}>
            <div className="card" style={{ background: 'var(--bg)' }}>
              <div className="faint">Scheduled for</div>
              <strong>{parsed.human_time}</strong>
            </div>
            <div className="card" style={{ background: 'var(--bg)' }}>
              <div className="faint">Confidence</div>
              <strong>{Math.round(parsed.confidence * 100)}%</strong>
            </div>
            <div className="card" style={{ background: 'var(--bg)' }}>
              <div className="faint">Interpretation</div>
              <strong style={{ fontSize: 12.5 }}>{parsed.interpretation}</strong>
            </div>
            <div className="card" style={{ background: 'var(--bg)' }}>
              <div className="faint">Timezone</div>
              <strong>{parsed.timezone}</strong>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Scheduled callbacks</div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>When (IST)</th>
                <th>Customer said</th>
                <th>Interpretation</th>
                <th>Confidence</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(callbacks || []).map((callback) => (
                <tr key={callback.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{callback.customer_name || 'Unknown'}</div>
                    <div className="faint mono">{callback.phone_number}</div>
                  </td>
                  <td><strong>{callback.human_time}</strong></td>
                  <td className="muted">{callback.original_text || '—'}</td>
                  <td className="faint">{callback.interpretation}</td>
                  <td>{Math.round((callback.confidence || 0) * 100)}%</td>
                  <td>
                    <span className={`chip ${callback.status === 'due' ? 'chip-accent' : ''}`}>
                      {callback.status}
                    </span>
                  </td>
                  <td>
                    {['scheduled', 'due'].includes(callback.status) && (
                      <div className="row">
                        <button className="btn-sm" onClick={() => updateStatus(callback.id, 'done')}>
                          Done
                        </button>
                        <button className="btn-sm btn-ghost" onClick={() => updateStatus(callback.id, 'cancelled')}>
                          Cancel
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!callbacks?.length && <div className="center-empty">No callbacks scheduled yet.</div>}
      </div>
    </div>
  )
}
