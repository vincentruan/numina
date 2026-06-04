import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useToolStatusText } from '../useToolStatusText'

// Mock vue-i18n so the composable can run outside a Vue app context
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

function makeOptions(
  toolType: string | undefined,
  elapsedMs: number,
  progressMessage?: string,
) {
  return {
    toolType: ref(toolType),
    elapsedMs: ref(elapsedMs),
    progressMessage: ref(progressMessage),
  }
}

describe('useToolStatusText', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Backend-driven progress message ──────────────────────────────────────

  it('returns progressMessage verbatim when truthy', () => {
    const opts = makeOptions('web_search', 1000, '正在分析页面内容...')
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('正在分析页面内容...')
  })

  it('falls through to inference when progressMessage is empty string', () => {
    const opts = makeOptions('web_search', 500, '')
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')
  })

  it('falls through to inference when progressMessage is undefined', () => {
    const opts = makeOptions('web_search', 500, undefined)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')
  })

  // ── web_search time brackets ──────────────────────────────────────────────

  it('web_search elapsed < 2000ms → short bracket', () => {
    const opts = makeOptions('web_search', 0)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')
  })

  it('web_search elapsed 1999ms → short bracket', () => {
    const opts = makeOptions('web_search', 1999)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')
  })

  it('web_search elapsed 2000ms → medium bracket', () => {
    const opts = makeOptions('web_search', 2000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.medium')
  })

  it('web_search elapsed 4999ms → medium bracket', () => {
    const opts = makeOptions('web_search', 4999)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.medium')
  })

  it('web_search elapsed 5000ms → long bracket', () => {
    const opts = makeOptions('web_search', 5000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.long')
  })

  it('web_search elapsed > 5000ms → long bracket', () => {
    const opts = makeOptions('web_search', 12000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.long')
  })

  // ── tavily_search (same group as web_search) ──────────────────────────────

  it('tavily_search routes to search group', () => {
    const opts = makeOptions('tavily_search', 500)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')
  })

  // ── code_interpreter time brackets ───────────────────────────────────────

  it('code_interpreter elapsed < 2000ms → short bracket', () => {
    const opts = makeOptions('code_interpreter', 1000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.code.short')
  })

  it('code_interpreter elapsed 2000-5000ms → medium bracket', () => {
    const opts = makeOptions('code_interpreter', 3000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.code.medium')
  })

  it('code_interpreter elapsed > 5000ms → long bracket', () => {
    const opts = makeOptions('code_interpreter', 8000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.code.long')
  })

  // ── bash (same code group) ────────────────────────────────────────────────

  it('bash routes to code group', () => {
    const opts = makeOptions('bash', 500)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.code.short')
  })

  // ── data tools ────────────────────────────────────────────────────────────

  it('get_assets routes to data group', () => {
    const opts = makeOptions('get_assets', 500)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.data.short')
  })

  it('get_dashboard_overview routes to data group', () => {
    const opts = makeOptions('get_dashboard_overview', 3000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.data.medium')
  })

  // ── file tools ────────────────────────────────────────────────────────────

  it('read_file routes to file group', () => {
    const opts = makeOptions('read_file', 500)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.file.short')
  })

  it('write_file routes to file group', () => {
    const opts = makeOptions('write_file', 6000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.file.long')
  })

  // ── unknown / generic tool type ───────────────────────────────────────────

  it('unknown tool type → generic short bracket', () => {
    const opts = makeOptions('some_unknown_tool', 500)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.generic.short')
  })

  it('unknown tool type → generic medium bracket', () => {
    const opts = makeOptions('some_unknown_tool', 3000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.generic.medium')
  })

  it('unknown tool type → generic long bracket', () => {
    const opts = makeOptions('some_unknown_tool', 7000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.generic.long')
  })

  it('undefined tool type → generic group', () => {
    const opts = makeOptions(undefined, 1000)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.generic.short')
  })

  // ── Reactivity: changing refs updates statusText ──────────────────────────

  it('statusText updates reactively when elapsedMs changes bracket', () => {
    const opts = makeOptions('web_search', 500)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')

    opts.elapsedMs.value = 3000
    expect(statusText.value).toBe('aiProcess.toolStatus.search.medium')

    opts.elapsedMs.value = 6000
    expect(statusText.value).toBe('aiProcess.toolStatus.search.long')
  })

  it('statusText updates reactively when progressMessage is set', () => {
    const opts = makeOptions('web_search', 500)
    const { statusText } = useToolStatusText(opts)
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')

    opts.progressMessage.value = '已找到 5 个相关页面'
    expect(statusText.value).toBe('已找到 5 个相关页面')

    opts.progressMessage.value = undefined
    expect(statusText.value).toBe('aiProcess.toolStatus.search.short')
  })
})
