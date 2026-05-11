import type { AgentEvent } from '@/types/agent-stream'

export function createAgentEventParser(onEvent: (event: AgentEvent) => void) {
  let buffer = ''

  function push(chunk: string) {
    buffer += chunk
    let newline = buffer.indexOf('\n')
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      try {
        if (line) onEvent(JSON.parse(line) as AgentEvent)
      } catch {
        // skip malformed NDJSON line
      }
      newline = buffer.indexOf('\n')
    }
  }

  function flush() {
    const line = buffer.trim()
    buffer = ''
    try {
      if (line) onEvent(JSON.parse(line) as AgentEvent)
    } catch {
      // skip malformed NDJSON line
    }
  }

  return { push, flush }
}
