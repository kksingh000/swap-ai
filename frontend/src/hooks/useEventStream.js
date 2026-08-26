import { useEffect, useRef } from 'react'

/**
 * Delivers every websocket event exactly once.
 *
 * A single `lastEvent` state slot silently drops events: React batches state
 * updates within a tick, so two events arriving together collapse into one and
 * the first is never seen. Mid-call that meant score updates and queued actions
 * vanished while the slower WhatsApp event (a separate tick) survived - the UI
 * looked like nothing had happened.
 *
 * Events carry a monotonic `_seq`, and this hook replays everything newer than
 * the last one it handled.
 */
export function useEventStream(events, handler) {
  const seenRef = useRef(0)
  const handlerRef = useRef(handler)

  useEffect(() => {
    handlerRef.current = handler
  })

  useEffect(() => {
    if (!events?.length) return
    for (const event of events) {
      if (event._seq > seenRef.current) {
        seenRef.current = event._seq
        handlerRef.current?.(event)
      }
    }
  }, [events])
}
