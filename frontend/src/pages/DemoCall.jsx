import { useEffect, useMemo, useRef, useState } from 'react'

import {
  ActionFeed,
  KeyValues,
  Reasons,
  ScoreGauge,
  WhatsAppSimulator,
  useToasts,
} from '../components/common'
import { useSpeechRecognition, useSpeechSynthesis } from '../hooks/useSpeech'
import { api } from '../services/api'

export default function DemoCall({ lastEvent, health }) {
  const [scenarios, setScenarios] = useState([])
  const [selected, setSelected] = useState(null)
  const [name, setName] = useState('')
  const [phoneMode, setPhoneMode] = useState(true)
  const [phoneNumber, setPhoneNumber] = useState('')

  const [call, setCall] = useState(null)
  const [messages, setMessages] = useState([])
  const [lead, setLead] = useState({ score: 0, classification: 'UNKNOWN', reasons: [] })
  const [memory, setMemory] = useState({})
  const [extracted, setExtracted] = useState(null)
  const [actions, setActions] = useState([])
  const [waMessages, setWaMessages] = useState([])
  const [thinking, setThinking] = useState(false)
  const [starting, setStarting] = useState(false)
  const [draft, setDraft] = useState('')
  const [autoPlaying, setAutoPlaying] = useState(false)

  const { push, host } = useToasts()
  const transcriptRef = useRef(null)
  const callRef = useRef(null)
  const tts = useSpeechSynthesis()

  useEffect(() => {
    api.scenarios().then((data) => setScenarios(data.scenarios || [])).catch(() => {})
  }, [])

  useEffect(() => {
    callRef.current = call
  }, [call])

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, thinking])

  // --- live events (background actions land here, not in the HTTP response) --
  useEffect(() => {
    if (!lastEvent || !callRef.current) return
    if (lastEvent.call_id && lastEvent.call_id !== callRef.current.call_id) return
    const { type, data } = lastEvent

    if (type === 'whatsapp.sent') {
      setWaMessages((current) => [...current, { ...data, at: Date.now() }])
      push(`WhatsApp ${data.simulated ? 'simulated' : 'sent'} → ${data.to}`, 'success')
      // The send happened in a background task, so close out its action card.
      setActions((current) =>
        current.map((action) =>
          action.action_id === data.action_id
            ? { ...action, status: data.error ? 'failed' : 'done' }
            : action,
        ),
      )
    }
    if (type === 'action.completed' || type === 'action.queued') {
      setActions((current) => {
        const rest = current.filter((a) => a.action_id !== data.action_id)
        return [...rest, data]
      })
    }
    if (type === 'callback.due') {
      push(`⏰ Callback due: ${data.customer_name || data.phone_number}`, 'warn')
    }
    // Phone-mode calls are driven by Twilio, so the transcript arrives over WS.
    if ((type === 'message.agent' || type === 'message.customer') && callRef.current.mode === 'phone') {
      setMessages((current) => {
        const last = current[current.length - 1]
        if (last && last.role === data.role && last.content === data.content) return current
        return [...current, { role: data.role, content: data.content, at: Date.now() }]
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  const handleRecognised = (text) => {
    if (text?.trim()) submitTurn(text.trim())
  }

  // Mic language mirrors whatever the backend detected from the customer's
  // last reply, starting from English. Never a manual choice.
  const detectedLanguage = memory.language || 'english'

  const speech = useSpeechRecognition({
    language: detectedLanguage,
    onResult: handleRecognised,
    onError: (error) => push(`Mic error: ${error}`, 'warn'),
  })

  async function startCall() {
    setStarting(true)
    try {
      const payload = phoneMode
        ? { customer_name: name || 'Customer', phone_number: phoneNumber }
        : { customer_name: name || undefined, scenario: selected?.id }

      const result = phoneMode ? await api.startPhoneCall(payload) : await api.startDemoCall(payload)

      setCall({
        call_id: result.call_id,
        customer: result.customer,
        mode: phoneMode ? 'phone' : 'demo',
        telephony: result.telephony,
      })
      setMessages([{ role: 'agent', content: result.opening_message, at: Date.now() }])
      setLead({ score: 0, classification: 'UNKNOWN', reasons: [] })
      setMemory({})
      setExtracted(null)
      setActions([])
      setWaMessages([])
      tts.speak(result.opening_message, 'english')

      if (phoneMode) {
        const status = result.telephony?.status
        push(
          status === 'failed'
            ? `Call failed: ${result.telephony.error}`
            : `Dialling ${result.customer.phone_number} (${result.telephony?.provider})`,
          status === 'failed' ? 'warn' : 'success',
        )
      }
    } catch (error) {
      push(error.message, 'warn')
    } finally {
      setStarting(false)
    }
  }

  async function submitTurn(text) {
    const active = callRef.current
    if (!active || thinking) return

    setMessages((current) => [...current, { role: 'customer', content: text, at: Date.now() }])
    setDraft('')
    setThinking(true)

    try {
      const result = await api.sendTurn(active.call_id, text)
      setMessages((current) => [...current, { role: 'agent', content: result.reply, at: Date.now() }])
      setLead(result.lead)
      setMemory(result.memory)
      setExtracted(result.extracted)
      setActions((current) => {
        const ids = new Set(current.map((a) => a.action_id))
        return [...current, ...result.actions.filter((a) => !ids.has(a.action_id))]
      })
      tts.speak(result.reply, result.memory?.language || 'english')

      if (result.should_end) {
        push('Agent closed the call.', 'info')
        setCall((current) => (current ? { ...current, ended: true } : current))
      }
      return result
    } catch (error) {
      push(error.message, 'warn')
      return null
    } finally {
      setThinking(false)
    }
  }

  async function endCall() {
    const active = callRef.current
    if (!active) return
    try {
      const result = await api.endCall(active.call_id)
      push(`Call ended · ${result.final_status} (${result.final_score}/100)`, 'success')
      setCall((current) => ({ ...current, ended: true, summary: result.summary }))
    } catch (error) {
      push(error.message, 'warn')
    }
  }

  async function autoPlay() {
    if (!selected?.utterances?.length || !callRef.current) return
    setAutoPlaying(true)
    for (const line of selected.utterances) {
      // Pause so a viewer can actually read each exchange.
      await new Promise((resolve) => setTimeout(resolve, 1500))
      const result = await submitTurn(line)
      if (result?.should_end) break
    }
    setAutoPlaying(false)
  }

  function reset() {
    tts.cancel()
    setCall(null)
    setMessages([])
    setActions([])
    setWaMessages([])
    setLead({ score: 0, classification: 'UNKNOWN', reasons: [] })
    setMemory({})
    setExtracted(null)
  }

  const memoryItems = useMemo(
    () => [
      ['Name', memory.customer_name],
      ['Intent', memory.intent],
      ['Budget', memory.budget ? `₹${memory.budget} ${memory.budget_qualifier || ''}`.trim() : null],
      ['Items', memory.clothing_categories],
      ['Brands', memory.brands],
      ['Size', memory.size],
      ['Timeline', memory.timeline?.replace(/_/g, ' ')],
      ['Location', memory.location],
      ['Barriers', memory.barriers?.map((b) => b.replace(/_/g, ' '))],
      ['Language', memory.language],
      ['Sentiment', memory.sentiment],
      ['Callback', memory.callback_requested ? 'requested' : null],
    ],
    [memory],
  )

  const telephony = health?.components?.telephony || {}
  const telephonyReady = Boolean(telephony.configured && telephony.live)

  // ---------------- Pre-call setup ----------------
  if (!call) {
    return (
      <div className="stack">
        {host}
        <div className="banner">
          <span>💡</span>
          <div>
            <strong>The agent always opens in English, then follows the customer.</strong> It
            detects English, Hindi or Hinglish from what the person actually says and switches to
            match them for the rest of the call — there is nothing to pick in advance. Browser demo
            mode runs the identical pipeline for free using the Web Speech API (Chrome or Edge).
          </div>
        </div>

        <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.3fr)' }}>
          <div className="card">
            <div className="card-title">Call setup</div>

            <div className="tabs" style={{ marginBottom: 16 }}>
              <button
                className={`tab ${phoneMode ? 'active' : ''}`}
                onClick={() => setPhoneMode(true)}
              >
                Real phone call
              </button>
              <button
                className={`tab ${!phoneMode ? 'active' : ''}`}
                onClick={() => setPhoneMode(false)}
              >
                Browser demo
              </button>
            </div>

            <div className="stack" style={{ gap: 13 }}>
              <div>
                <label>Customer name</label>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={selected?.customer_name || 'Rahul'}
                />
              </div>

              {phoneMode && (
                <>
                  <div>
                    <label>Phone number (E.164)</label>
                    <input
                      value={phoneNumber}
                      onChange={(event) => setPhoneNumber(event.target.value)}
                      placeholder="+919812345678"
                    />
                  </div>
                  {telephonyReady ? (
                    <div className="banner">
                      <span>&#9989;</span>
                      <div>
                        Dialling for real via <strong>{telephony.provider}</strong> from{' '}
                        <span className="mono">{telephony.from}</span>. On a Twilio trial the
                        destination must be a verified caller ID.
                      </div>
                    </div>
                  ) : (
                    <div className="banner warn">
                      <span>&#9888;</span>
                      <div>
                        <strong>Real calling is unavailable.</strong>{' '}
                        {health
                          ? `Backend telephony is '${telephony.provider || 'mock'}'.`
                          : 'The dashboard cannot reach the backend.'}{' '}
                        The API refuses these requests rather than faking a call.
                      </div>
                    </div>
                  )}
                </>
              )}

              <button
                className="btn-primary"
                onClick={startCall}
                disabled={starting || (phoneMode && (!phoneNumber || !telephonyReady))}
                style={{ justifyContent: 'center' }}
              >
                {starting ? 'Starting…' : phoneMode ? '📞 Place call' : '🎙️ Start demo call'}
              </button>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Scenarios (optional script for the customer side)</div>
            <div className="stack" style={{ gap: 9 }}>
              {scenarios.map((scenario) => (
                <div
                  key={scenario.id}
                  className={`scenario-card ${selected?.id === scenario.id ? 'selected' : ''}`}
                  onClick={() => {
                    const next = selected?.id === scenario.id ? null : scenario
                    setSelected(next)
                    if (next) setName(next.customer_name)
                  }}
                >
                  <div className="between">
                    <strong style={{ fontSize: 13 }}>{scenario.label}</strong>
                    <span className={`badge badge-${scenario.expected}`}>{scenario.expected}</span>
                  </div>
                  <div className="faint" style={{ marginTop: 3 }}>{scenario.description}</div>
                </div>
              ))}
              {!scenarios.length && <div className="center-empty">Loading scenarios…</div>}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ---------------- In-call ----------------
  return (
    <div className="stack">
      {host}

      <div className="card">
        <div className="between">
          <div className="row">
            <span className={`dot ${call.ended ? 'dot-off' : 'dot-live'}`} />
            <div>
              <div style={{ fontWeight: 700 }}>
                {call.ended ? 'CALL ENDED' : 'CALL ACTIVE'} ·{' '}
                {call.customer?.name || 'Customer'}
              </div>
              <div className="faint">
                {call.customer?.phone_number} · {call.mode === 'phone' ? 'Phone' : 'Browser demo'} · call
                #{call.call_id}
              </div>
            </div>
          </div>
          <div className="row">
            <button className="btn-sm" onClick={() => tts.setEnabled(!tts.enabled)}>
              {tts.enabled ? '🔊 Voice on' : '🔇 Voice off'}
            </button>
            {selected && !call.ended && (
              <button className="btn-sm" onClick={autoPlay} disabled={autoPlaying || thinking}>
                {autoPlaying ? '▶ Playing…' : '▶ Auto-play scenario'}
              </button>
            )}
            {!call.ended && (
              <button className="btn-sm btn-danger" onClick={endCall}>
                End call
              </button>
            )}
            <button className="btn-sm" onClick={reset}>
              New call
            </button>
          </div>
        </div>
        {call.summary && (
          <div className="banner" style={{ marginTop: 14 }}>
            <span>📝</span>
            <div>
              <strong>Call summary:</strong> {call.summary}
            </div>
          </div>
        )}
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.5fr) minmax(0, 1fr)' }}>
        {/* ---- Conversation ---- */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-title">Live transcript</div>

          <div className="transcript" ref={transcriptRef}>
            {messages.map((message, index) => (
              <div
                key={index}
                className={`bubble ${message.role === 'agent' ? 'bubble-agent' : 'bubble-customer'}`}
              >
                <div className="bubble-body">{message.content}</div>
                <div className="bubble-meta">
                  {message.role === 'agent' ? '🤖 Ananya' : '👤 Customer'} ·{' '}
                  {new Date(message.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            ))}
            {thinking && (
              <div className="bubble bubble-agent">
                <div className="bubble-body">
                  <span className="typing">
                    <span />
                    <span />
                    <span />
                  </span>
                </div>
              </div>
            )}
            {speech.interim && (
              <div className="bubble bubble-customer">
                <div className="bubble-body" style={{ opacity: 0.6 }}>{speech.interim}…</div>
              </div>
            )}
          </div>

          {!call.ended && call.mode !== 'phone' && (
            <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
              <div className="row" style={{ alignItems: 'flex-end' }}>
                <button
                  className={`mic-btn ${speech.listening ? 'listening' : ''}`}
                  onClick={() => (speech.listening ? speech.stop() : speech.start())}
                  disabled={!speech.supported || thinking}
                  title={speech.supported ? 'Hold a conversation with your mic' : 'Web Speech API not supported'}
                >
                  {speech.listening ? '⏹' : '🎤'}
                </button>
                <form
                  style={{ flex: 1 }}
                  onSubmit={(event) => {
                    event.preventDefault()
                    if (draft.trim()) submitTurn(draft.trim())
                  }}
                >
                  <input
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={
                      speech.listening
                        ? 'Listening…'
                        : 'Type what the customer says, or press the mic and speak'
                    }
                    disabled={thinking}
                  />
                </form>
                <button
                  className="btn-primary"
                  onClick={() => draft.trim() && submitTurn(draft.trim())}
                  disabled={thinking || !draft.trim()}
                >
                  Send
                </button>
              </div>
              {!speech.supported && (
                <div className="faint" style={{ marginTop: 8 }}>
                  Your browser has no Web Speech API — use the text box (Chrome/Edge for voice).
                </div>
              )}
            </div>
          )}

          {call.mode === 'phone' && (
            <div className="banner" style={{ marginTop: 16 }}>
              <span>📞</span>
              <div>
                This call is running over the phone network. The transcript streams in live as the
                customer speaks.
              </div>
            </div>
          )}
        </div>

        {/* ---- Live intelligence ---- */}
        <div className="stack">
          <div className="card">
            <div className="card-title">Lead score</div>
            <ScoreGauge score={lead.score} status={lead.classification} />
            <div style={{ marginTop: 16 }}>
              <Reasons reasons={lead.reasons} />
            </div>
          </div>

          <div className="card">
            <div className="card-title">Extracted information</div>
            <KeyValues items={memoryItems} />
            {extracted && (
              <div className="wrap" style={{ marginTop: 12 }}>
                <span className="chip chip-accent">intent: {extracted.intent}</span>
                <span className="chip">lang: {extracted.language}</span>
                <span className="chip">buying intent: {Math.round(extracted.buying_intent * 100)}%</span>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-title">Live actions</div>
            <ActionFeed actions={actions} />
          </div>

          <div className="card" style={{ padding: 0, background: 'transparent', border: 'none' }}>
            <div className="card-title" style={{ paddingLeft: 2 }}>WhatsApp simulator</div>
            <WhatsAppSimulator messages={waMessages} customerName={call.customer?.name || 'Customer'} />
          </div>
        </div>
      </div>
    </div>
  )
}
