import { computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

export interface UseToolStatusTextOptions {
  toolType: Ref<string | undefined>
  elapsedMs: Ref<number>
  progressMessage: Ref<string | undefined>
}

// Time thresholds for status text buckets (ms)
const THRESHOLD_SHORT = 2000
const THRESHOLD_MEDIUM = 5000

// Tool type groups for status text routing
const SEARCH_TOOLS = new Set(['web_search', 'tavily_search'])
const DATA_TOOLS = new Set([
  'get_assets',
  'get_asset_list',
  'get_dashboard_overview',
  'get_dashboard_allocation',
  'get_low_usage_assets',
])
const FILE_TOOLS = new Set(['read_file', 'write_file'])
const CODE_TOOLS = new Set(['bash', 'code_interpreter'])

function getToolGroup(
  toolType: string | undefined,
): 'search' | 'data' | 'file' | 'code' | 'generic' {
  if (!toolType) return 'generic'
  if (SEARCH_TOOLS.has(toolType)) return 'search'
  if (DATA_TOOLS.has(toolType)) return 'data'
  if (FILE_TOOLS.has(toolType)) return 'file'
  if (CODE_TOOLS.has(toolType)) return 'code'
  return 'generic'
}

export function useToolStatusText(options: UseToolStatusTextOptions) {
  const { toolType, elapsedMs, progressMessage } = options
  const { t } = useI18n()

  const statusText = computed((): string => {
    // Backend-driven progress message takes highest priority
    if (progressMessage.value) return progressMessage.value

    const elapsed = elapsedMs.value
    const group = getToolGroup(toolType.value)

    // Select time bracket: short (0-2s), medium (2-5s), long (5s+)
    let bracket: 'short' | 'medium' | 'long'
    if (elapsed < THRESHOLD_SHORT) {
      bracket = 'short'
    } else if (elapsed < THRESHOLD_MEDIUM) {
      bracket = 'medium'
    } else {
      bracket = 'long'
    }

    return t(`aiProcess.toolStatus.${group}.${bracket}`)
  })

  return { statusText }
}
