import { describe, expect, it } from 'vitest'

import { createAgentEventParser } from '../../../src/composables/useAgentEventStream'

describe('createAgentEventParser', () => {
  it('parses complete and split NDJSON lines', () => {
    const events: unknown[] = []
    const parser = createAgentEventParser((event) => events.push(event))

    parser.push('{"type":"phase.connecting","phase":"connecting"}\n{"type":"token.stream"')
    parser.push(',"token":"净资产","is_thinking":false}\n')
    parser.flush()

    expect(events).toEqual([
      { type: 'phase.connecting', phase: 'connecting' },
      { type: 'token.stream', token: '净资产', is_thinking: false },
    ])
  })
})
