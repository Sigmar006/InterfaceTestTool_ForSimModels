import { useEffect, useRef, useState } from 'react'

const WS_BASE = 'ws://localhost:8000/api/v1/ws'

/**
 * Custom hook to connect to the backend WebSocket for a specific run.
 * @param {string|null} runId - The run ID to connect to
 * @param {function} onMessage - Callback for each parsed JSON message
 * @returns {{ connected: boolean, error: string|null }}
 */
export function useWebSocket(runId, onMessage) {
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)
  const onMessageRef = useRef(onMessage)

  // Keep the callback ref up to date without triggering reconnects
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    if (!runId) {
      return
    }

    const url = `${WS_BASE}/${runId}`
    let ws

    try {
      ws = new WebSocket(url)
    } catch (err) {
      setError(`Failed to create WebSocket: ${err.message}`)
      return
    }

    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessageRef.current(data)
      } catch (err) {
        console.warn('WebSocket: failed to parse message', event.data, err)
      }
    }

    ws.onerror = (event) => {
      setError('WebSocket error occurred')
      setConnected(false)
    }

    ws.onclose = (event) => {
      setConnected(false)
      if (!event.wasClean) {
        setError(`WebSocket closed unexpectedly (code: ${event.code})`)
      }
    }

    return () => {
      ws.onopen = null
      ws.onmessage = null
      ws.onerror = null
      ws.onclose = null
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
      wsRef.current = null
      setConnected(false)
    }
  }, [runId])

  return { connected, error }
}
