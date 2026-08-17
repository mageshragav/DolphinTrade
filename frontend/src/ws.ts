import { useEffect, useRef, useState } from 'react'

export type WSMessage =
  | { type: 'status'; running: boolean }
  | { type: 'decision'; action: string; symbol: string; tf?: string; expiry?: string;
      best_prob?: number; entry_price?: number | null; target_price?: number | null;
      stop_loss?: number | null; candle_open?: number | null; candle_close_price?: number | null;
      ts?: string; [k: string]: unknown }
  | { type: 'trade'; trade: Record<string, unknown> }
  | { type: 'trade_settled'; trade: Record<string, unknown> }
  | { type: 'agent'; line: string; ts?: number }
  | { type: 'alert'; message: string }
  | { type: 'log'; line: string; ts?: number }

export function useWebSocket(onMessage: (m: WSMessage) => void) {
  const cbRef = useRef(onMessage)
  cbRef.current = onMessage
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let ws: WebSocket | null = null
    let retry = 0
    let closed = false

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/api/ws`)
      ws.onopen = () => { setConnected(true); retry = 0 }
      ws.onclose = () => {
        setConnected(false)
        if (!closed && retry < 10) {
          setTimeout(connect, Math.min(1000 * 2 ** retry, 15000))
          retry++
        }
      }
      ws.onerror = () => ws?.close()
      ws.onmessage = (e) => {
        try { cbRef.current(JSON.parse(e.data) as WSMessage) } catch { /* ignore */ }
      }
    }
    connect()
    return () => { closed = true; ws?.close() }
  }, [])

  return connected
}
