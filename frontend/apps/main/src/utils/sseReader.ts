/**
 * Shared SSE stream reader — parses Server-Sent Events from a fetch Response
 * and dispatches parsed frames to typed callbacks.
 *
 * Extracted from useReportStream / useLiteracyStream / dashboard.runNarrativeStream
 * to eliminate ~80 lines of identical SSE line-parsing logic per consumer.
 *
 * The bridge consumer wraps each event as:
 *   event: {type}
 *   data: {"type":"...","data":{...}}
 *
 * So the actual payload lives in `parsed.data`; the helper auto-unwraps via
 * `parsed.data ?? parsed` so consumers always receive the inner payload.
 */

/**
 * Event handlers for the SSE reader.  `onMessage`, `onCustom`, and `onEnd`
 * are required; the rest are optional.
 */
export interface SSEStreamHandlers {
  /** messages / values frames (LangGraph wire format). */
  onMessage: (event: string, data: unknown) => void
  /** custom frames (skill results, reasoning deltas, tool events). */
  onCustom: (data: unknown) => void
  /** error frames. */
  onError: (data: unknown) => void
  /**
   * end frame.  ``data`` is the end payload when present, ``undefined``
   * when the bridge sent ``data: null`` (the common sentinel).
   */
  onEnd: (data: unknown) => void
  /** metadata frames (run_id, progress).  Default: no-op. */
  onMetadata?: (data: unknown) => void
  /** gap frames (stream replay cursor beyond retained buffer).  Default: no-op. */
  onGap?: (data: unknown) => void
}

/**
 * Read an SSE stream from a fetch ``Response``, parsing each frame and
 * dispatching to the supplied handlers.
 *
 * Resolves when the stream ends naturally (``reader.read()`` returns
 * ``done: true``).  Rejects on network / decode errors — ``AbortError``
 * propagates so callers can distinguish user cancellation from real failures.
 *
 * @param response  A fetch ``Response`` whose body is an SSE byte stream.
 * @param handlers  Typed callbacks for each SSE event category.
 */
export async function readSSEStream(
  response: Response,
  handlers: SSEStreamHandlers,
): Promise<void> {
  const body = response.body
  if (!body) return

  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
          continue
        }
        if (!line.startsWith('data:')) continue
        const dataStr = line.slice(5).trim()
        // Skip empty lines, [DONE] sentinels, and null sentinels.
        // The bridge consumer sends ``data: null`` for the end sentinel;
        // the ``currentEvent === 'end'`` check below dispatches it to onEnd.
        if (!dataStr || dataStr === '[DONE]' || dataStr === 'null') {
          if (currentEvent === 'end') handlers.onEnd(undefined)
          currentEvent = ''
          continue
        }

        try {
          const parsed = JSON.parse(dataStr) as Record<string, unknown>
          // Auto-unwrap: bridge wraps as {event, data}; consumers want the
          // inner payload.  Falls back to the parsed object itself when the
          // wrapper has no ``data`` field (direct payload format).
          const data = (parsed.data as unknown) ?? parsed
          const event = currentEvent || (parsed.event as string) || 'message'
          currentEvent = ''

          switch (event) {
            case 'metadata':
              handlers.onMetadata?.(data)
              break
            case 'messages':
            case 'values':
              handlers.onMessage(event, data)
              break
            case 'custom':
              handlers.onCustom(data)
              break
            case 'error':
              handlers.onError(data)
              break
            case 'gap':
              handlers.onGap?.(data)
              break
            case 'end':
              handlers.onEnd(data)
              break
            default:
              // Unknown event type — ignore (forward-compatible).
              break
          }
        } catch {
          // Non-JSON data line; skip (best-effort).
        }
        currentEvent = ''
      }
    }
  } finally {
    // Release the reader lock so the response can be garbage-collected.
    try {
      reader.releaseLock()
    } catch {
      // Already released or locked elsewhere — ignore.
    }
  }
}
