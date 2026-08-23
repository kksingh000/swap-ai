import { useEffect, useRef, useState } from 'react'
import { websocketUrl } from '../services/api'

/**
 * Live channel to the backend event bus, with automatic reconnect.
 * `onEvent` is kept in a ref so re-renders never tear down the socket.
 */
export function useWebSocket(onEvent) {
  const [connected, setConnected] = useState(false)
  const handlerRef = useRef(onEvent)
  const socketRef = useRef(null)
  const retryRef = useRef(0)
  const closedRef = useRef(false)

  useEffect(() => {
    handlerRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    closedRef.current = false
    let timer

    const connect = () => {
      if (closedRef.current) return
      const socket = new WebSocket(websocketUrl())
      socketRef.current = socket

      socket.onopen = () => {
        setConnected(true)
        retryRef.current = 0
      }
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handlerRef.current?.(message)
        } catch {
          /* ignore malformed frames */
        }
      }
      socket.onclose = () => {
        setConnected(false)
        if (closedRef.current) return
        retryRef.current = Math.min(retryRef.current + 1, 6)
        timer = setTimeout(connect, 600 * retryRef.current)
      }
      socket.onerror = () => socket.close()
    }

    connect()
    return () => {
      closedRef.current = true
      clearTimeout(timer)
      socketRef.current?.close()
    }
  }, [])

  return { connected }
}
