import { useEffect, useState } from 'react'

export function LeadBadge({ status, size }) {
  const value = (status || 'UNKNOWN').toUpperCase()
  const icon = { HOT: '🔥', WARM: '🌤️', COLD: '❄️', UNKNOWN: '•' }[value] || '•'
  return (
    <span className={`badge badge-${value}`} style={size === 'lg' ? { fontSize: 13, padding: '5px 12px' } : undefined}>
      {icon} {value}
    </span>
  )
}

export function StatCard({ label, value, icon, tone }) {
  return (
    <div className={`card stat ${tone ? `stat-${tone}` : ''}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-value">{value ?? 0}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

const SCORE_COLOR = (score) => {
  if (score >= 60) return 'var(--hot)'
  if (score >= 20) return 'var(--warm)'
  return 'var(--cold)'
}

export function ScoreGauge({ score = 0, status = 'UNKNOWN' }) {
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (Math.max(0, Math.min(100, score)) / 100) * circumference

  return (
    <div className="gauge">
      <div className="gauge-ring">
        <svg width="96" height="96">
          <circle cx="48" cy="48" r={radius} fill="none" stroke="var(--bg)" strokeWidth="8" />
          <circle
            cx="48"
            cy="48"
            r={radius}
            fill="none"
            stroke={SCORE_COLOR(score)}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(.22,1,.36,1), stroke 0.4s' }}
          />
        </svg>
        <div className="gauge-ring-text">
          <div style={{ textAlign: 'center' }}>
            {score}
            <br />
            <small>/ 100</small>
          </div>
        </div>
      </div>
      <div>
        <LeadBadge status={status} size="lg" />
        <div className="faint" style={{ marginTop: 8 }}>
          Lead score updates after every customer reply.
        </div>
      </div>
    </div>
  )
}

export function ScoreBar({ score = 0 }) {
  return (
    <div className="score-bar" style={{ width: 78 }}>
      <div
        className="score-bar-fill"
        style={{ width: `${Math.max(2, Math.min(100, score))}%`, background: SCORE_COLOR(score) }}
      />
    </div>
  )
}

export function Reasons({ reasons = [] }) {
  if (!reasons.length) return <div className="faint">No signals detected yet.</div>
  return (
    <div className="reason-list">
      {reasons.map((reason, index) => {
        const negative = /\(-\d+\)/.test(reason)
        return (
          <div className="reason" key={index}>
            <span className={`reason-mark ${negative ? 'neg' : ''}`}>{negative ? '−' : '✓'}</span>
            <span>{reason}</span>
          </div>
        )
      })}
    </div>
  )
}

const ACTION_META = {
  send_whatsapp: { icon: '💬', label: 'WhatsApp sent' },
  schedule_callback: { icon: '📅', label: 'Callback scheduled' },
  mark_do_not_call: { icon: '🚫', label: 'Marked do-not-call' },
  end_call: { icon: '📴', label: 'Call closed' },
}

export function ActionFeed({ actions = [] }) {
  if (!actions.length) {
    return <div className="center-empty">No actions triggered yet.</div>
  }
  return (
    <div>
      {actions.map((action, index) => {
        const meta = ACTION_META[action.action_type] || { icon: '⚡', label: action.action_type }
        const status = action.status || 'queued'
        return (
          <div className="action-item" key={action.action_id || action.id || index}>
            <div className={`action-icon ${status === 'done' ? 'done' : status === 'failed' ? 'failed' : ''}`}>
              {meta.icon}
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="between">
                <strong style={{ fontSize: 13 }}>{meta.label}</strong>
                <span className={`chip ${status === 'done' ? 'chip-good' : ''}`}>{status}</span>
              </div>
              <div className="faint">{action.reason || action.trigger_reason}</div>
              {action.result?.human_time && (
                <div className="faint" style={{ marginTop: 2 }}>
                  ⏰ {action.result.human_time}
                  {action.result.interpretation ? ` · ${action.result.interpretation}` : ''}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

const FAILED_WA_STATUS = new Set(['failed', 'undelivered'])

// Twilio's create response says "queued" - that is acceptance, not delivery.
// Showing a permanent double tick made a rejected message look delivered.
function waStatusLabel(message) {
  if (message.simulated) return '✓✓ simulated'
  const status = message.status || 'queued'
  if (FAILED_WA_STATUS.has(status)) return `✗ ${status}`
  if (status === 'delivered') return '✓✓ delivered'
  if (status === 'read') return '✓✓ read'
  if (status === 'sent') return '✓ sent'
  return `◷ ${status}`
}

export function WhatsAppSimulator({ messages = [], customerName = 'Customer' }) {
  return (
    <div className="wa-phone">
      <div className="wa-header">
        <div className="wa-avatar">👤</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#e9edef' }}>{customerName}</div>
          <div style={{ fontSize: 11, color: '#8696a0' }}>SwapCircle Business</div>
        </div>
      </div>
      <div className="wa-body">
        {messages.length === 0 ? (
          <div className="wa-empty">
            No messages yet.
            <br />
            The agent sends one automatically when a lead turns hot.
          </div>
        ) : (
          messages.map((message, index) => (
            <div
              className="wa-msg"
              key={message.message_id || message.id || index}
              style={
                FAILED_WA_STATUS.has(message.status)
                  ? { background: '#5c1f1f', border: '1px solid rgba(239,68,68,0.5)' }
                  : undefined
              }
            >
              {message.body}
              {FAILED_WA_STATUS.has(message.status) && message.error && (
                <div style={{ marginTop: 8, fontSize: 11.5, color: '#fca5a5' }}>
                  ⚠ {message.error}
                </div>
              )}
              <div className="wa-time">
                {waStatusLabel(message)} ·{' '}
                {new Date(message.at || Date.now()).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export function KeyValues({ items }) {
  const rows = items.filter(([, value]) => value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && !value.length))
  if (!rows.length) return <div className="faint">Nothing captured yet.</div>
  return (
    <div>
      {rows.map(([key, value]) => (
        <div className="kv" key={key}>
          <span className="kv-key">{key}</span>
          <span className="kv-val">{Array.isArray(value) ? value.join(', ') : String(value)}</span>
        </div>
      ))}
    </div>
  )
}

export function useToasts() {
  const [toasts, setToasts] = useState([])

  const push = (message, tone = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((current) => [...current, { id, message, tone }])
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 4200)
  }

  const host = (
    <div className="toast-host">
      {toasts.map((toast) => (
        <div className={`toast ${toast.tone}`} key={toast.id}>
          {toast.message}
        </div>
      ))}
    </div>
  )

  return { push, host }
}

export function useFetch(loader, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const reload = () => {
    setLoading(true)
    loader()
      .then((result) => {
        setData(result)
        setError(null)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let alive = true
    setLoading(true)
    loader()
      .then((result) => alive && (setData(result), setError(null)))
      .catch((err) => alive && setError(err.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading, reload, setData }
}
