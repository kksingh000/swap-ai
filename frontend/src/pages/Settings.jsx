import { useEffect, useState } from 'react'

import { useToasts } from '../components/common'
import { api } from '../services/api'

export default function Settings({ health, onHealth }) {
  const [config, setConfig] = useState(null)
  const [providers, setProviders] = useState(null)
  const [profileDraft, setProfileDraft] = useState({})
  const [weightsDraft, setWeightsDraft] = useState({})
  const [busy, setBusy] = useState(false)
  const { push, host } = useToasts()

  useEffect(() => {
    api.storeConfig().then((data) => {
      setConfig(data)
      setProfileDraft(data.profile || {})
      setWeightsDraft(data.scoring_weights || {})
    })
    api.providers().then(setProviders).catch(() => {})
  }, [])

  async function save() {
    setBusy(true)
    try {
      const updated = await api.patchStoreConfig({
        profile: profileDraft,
        scoring_weights: Object.fromEntries(
          Object.entries(weightsDraft).map(([key, value]) => [key, Number(value)]),
        ),
      })
      setConfig(updated)
      push('Configuration saved', 'success')
    } catch (error) {
      push(error.message, 'warn')
    } finally {
      setBusy(false)
    }
  }

  async function switchProvider(kind, value) {
    try {
      await api.switchProvider({ [kind]: value })
      push(`${kind} → ${value}`, 'success')
      const [nextHealth, nextProviders] = await Promise.all([api.health(), api.providers()])
      onHealth?.(nextHealth)
      setProviders(nextProviders)
    } catch (error) {
      push(error.message, 'warn')
    }
  }

  if (!config) return <div className="center-empty">Loading configuration…</div>

  const components = health?.components || {}

  return (
    <div className="stack">
      {host}

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title">Store profile</div>
          <div className="stack" style={{ gap: 11 }}>
            {['store_name', 'agent_name', 'location', 'catalog_url', 'swap_event'].map((field) => (
              <div key={field}>
                <label>{field.replace(/_/g, ' ')}</label>
                <input
                  value={profileDraft[field] || ''}
                  onChange={(event) =>
                    setProfileDraft({ ...profileDraft, [field]: event.target.value })
                  }
                />
              </div>
            ))}
            <button className="btn-primary" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : 'Save configuration'}
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Lead scoring weights</div>
          <div className="faint" style={{ marginBottom: 12 }}>
            Business rules, not model weights — change them and every future call is scored differently.
          </div>
          <div style={{ maxHeight: 340, overflowY: 'auto', paddingRight: 6 }}>
            {Object.entries(weightsDraft).map(([signal, value]) => (
              <div className="kv" key={signal}>
                <span className="kv-key">{signal.replace(/_/g, ' ')}</span>
                <input
                  type="number"
                  value={value}
                  onChange={(event) => setWeightsDraft({ ...weightsDraft, [signal]: event.target.value })}
                  style={{ width: 78, padding: '4px 8px', textAlign: 'right' }}
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Providers</div>
        <div className="faint" style={{ marginBottom: 14 }}>
          Every integration sits behind an interface, so you can hot-swap it here. Credentials still
          come from <code>.env</code> — nothing secret is editable from the browser.
        </div>

        <div className="grid grid-3">
          <div>
            <label>LLM</label>
            <select
              value={providers?.llm?.active || 'rules'}
              onChange={(event) => switchProvider('llm', event.target.value)}
            >
              {(providers?.llm?.options || []).map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <div className="faint" style={{ marginTop: 6 }}>
              {components.llm?.available
                ? `active: ${components.llm.provider} (${components.llm.model || 'n/a'})`
                : 'deterministic mode — rules NLU + template replies'}
            </div>
          </div>

          <div>
            <label>Telephony</label>
            <select
              value={providers?.telephony?.active || 'mock'}
              onChange={(event) => switchProvider('telephony', event.target.value)}
            >
              {(providers?.telephony?.options || []).map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <div className="faint" style={{ marginTop: 6 }}>
              {components.telephony?.configured === false
                ? 'Twilio credentials missing'
                : `active: ${components.telephony?.provider}`}
            </div>
          </div>

          <div>
            <label>WhatsApp</label>
            <select
              value={providers?.whatsapp?.active || 'mock'}
              onChange={(event) => switchProvider('whatsapp', event.target.value)}
            >
              {(providers?.whatsapp?.options || []).map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <div className="faint" style={{ marginTop: 6 }}>
              active: {components.whatsapp?.provider} ({components.whatsapp?.live ? 'live' : 'simulated'})
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">System health</div>
        <div className="grid grid-4">
          <div className="card" style={{ background: 'var(--bg)' }}>
            <div className="faint">Cost mode</div>
            <strong>{health?.cost_mode || 'FREE'}</strong>
          </div>
          <div className="card" style={{ background: 'var(--bg)' }}>
            <div className="faint">Database</div>
            <strong>{components.database?.url || 'sqlite'}</strong>
          </div>
          <div className="card" style={{ background: 'var(--bg)' }}>
            <div className="faint">Classifier</div>
            <strong>
              {components.classifier?.loaded
                ? `${(components.classifier.accuracy * 100).toFixed(1)}% accuracy`
                : 'not trained'}
            </strong>
          </div>
          <div className="card" style={{ background: 'var(--bg)' }}>
            <div className="faint">Scheduler</div>
            <strong>{components.scheduler?.timezone || 'Asia/Kolkata'}</strong>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Knowledge base (used for objection handling)</div>
        {(config.faq || []).map((entry, index) => (
          <div className="kv" key={index} style={{ display: 'block' }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{entry.q}</div>
            <div className="faint" style={{ marginTop: 3 }}>{entry.a}</div>
            {entry.a_hinglish && (
              <div className="faint" style={{ marginTop: 2, fontStyle: 'italic' }}>{entry.a_hinglish}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
