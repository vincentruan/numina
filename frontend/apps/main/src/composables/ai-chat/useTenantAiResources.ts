/**
 * DeerFlow Tenant AI Resources Composable
 *
 * 参考: frontend/src/components/workspace/input-box.tsx useTenantAiResources
 *
 * 职责:
 * - 获取租户过滤后的模型列表
 * - 检查租户能力限制 (subagent, websearch)
 * - 提供模型能力判断
 *
 * 安全保证:
 * - 前端选择仅作为用户意图
 * - 后端必须基于 family/tenant/user 重算最终可用配置
 * - 如果后端返回降级结果，前端要显示提示
 */

import { ref, computed, onMounted, type Ref, type ComputedRef } from 'vue'
import { showFailToast } from 'vant'
import i18n from '@/i18n'
import http from '@/api'
import { useFamilyStore } from '@/stores/family'
import { getMCPServers, type MCPServer } from '@/api/ai'

// i18n helper
function t(key: string, params?: Record<string, unknown>): string {
  return i18n.global.t(key, params ?? {})
}

/**
 * DeerFlow-aligned Model Info
 *
 * 参考: backend/app/schemas/ai_config.py ModelInfo
 */
export interface ModelInfo {
  name: string
  display_name: string
  provider: string
  provider_name: string
  supports_thinking: boolean
  supports_vision: boolean
  supports_tool_calling: boolean
  is_default: boolean
  config_id: string
}

/**
 * Tenant AI Config response
 */
export interface TenantAiConfig {
  subagent_enabled: boolean
  websearch_enabled: boolean
}

/**
 * API Response from /api/v1/ai/models
 */
interface ModelsApiResponse {
  models: ModelInfo[]
  subagent_enabled: boolean
  websearch_enabled: boolean
}

/**
 * useTenantAiResources Composable
 *
 * Returns:
 * - models: 租户过滤后的模型列表
 * - tenantConfig: 租户能力配置
 * - loading/error: 加载状态
 * - supportsThinking/subagent/websearch: 计算的能力支持
 * - defaultModel: 默认模型
 * - getModelCapabilities: 模型能力查询
 * - isModeAvailable: 执行模式可用性检查
 */
export function useTenantAiResources(): {
  models: Ref<ModelInfo[]>
  tenantConfig: Ref<TenantAiConfig>
  loading: Ref<boolean>
  error: Ref<string | null>
  supportsThinking: ComputedRef<boolean>
  supportsSubagent: ComputedRef<boolean>
  supportsWebSearch: ComputedRef<boolean>
  hasWebSearchMcp: ComputedRef<boolean>
  webSearchAvailable: ComputedRef<boolean>
  defaultModel: ComputedRef<ModelInfo | undefined>
  loadResources: () => Promise<void>
  getModelCapabilities: (modelName: string) => {
    supportsThinking: boolean
    supportsVision: boolean
    supportsToolCalling: boolean
  }
  isModeAvailable: (
    mode: 'flash' | 'thinking' | 'pro' | 'ultra',
    modelName: string,
  ) => boolean
} {
  const familyStore = useFamilyStore()
  const familyId = computed(() => familyStore.family?.id)

  const models = ref<ModelInfo[]>([])
  const mcpServers = ref<MCPServer[]>([])
  const tenantConfig = ref<TenantAiConfig>({
    subagent_enabled: false,
    websearch_enabled: false,
  })
  const loading = ref(true)
  const error = ref<string | null>(null)

  // 计算能力支持
  const supportsThinking = computed(() =>
    models.value.some(m => m.supports_thinking),
  )

  const supportsSubagent = computed(() =>
    tenantConfig.value.subagent_enabled,
  )

  const supportsWebSearch = computed(() =>
    tenantConfig.value.websearch_enabled,
  )

  // 联网搜索 MCP：mcp_type == "websearch" 且 is_enabled 的 MCP server
  const hasWebSearchMcp = computed(() =>
    mcpServers.value.some((s) => s.mcp_type === 'websearch' && s.is_enabled),
  )

  // 联网搜索可用 = 启用了联网搜索配置 或 启用了联网搜索 MCP
  const webSearchAvailable = computed(() =>
    supportsWebSearch.value || hasWebSearchMcp.value,
  )

  // 默认模型
  const defaultModel = computed(() =>
    models.value.find(m => m.is_default) ?? models.value[0],
  )

  /**
   * 加载租户 AI 资源
   */
  async function loadResources(): Promise<void> {
    if (!familyId.value) {
      error.value = t('aiChat.tenantNoFamily')
      loading.value = false
      return
    }

    loading.value = true
    error.value = null

    try {
      const [response, mcpRes] = await Promise.all([
        http.get<ModelsApiResponse>('/ai/models'),
        getMCPServers().then((res) => res.data).catch(() => [] as MCPServer[]),
      ])
      models.value = response.data.models
      mcpServers.value = mcpRes
      tenantConfig.value = {
        subagent_enabled: response.data.subagent_enabled,
        websearch_enabled: response.data.websearch_enabled,
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : t('common.failed')
      showFailToast(t('aiChat.loadModelsFailed', { error: error.value }))
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取模型能力
   */
  function getModelCapabilities(modelName: string): {
    supportsThinking: boolean
    supportsVision: boolean
    supportsToolCalling: boolean
  } {
    const model = models.value.find(m => m.name === modelName)
    return {
      supportsThinking: model?.supports_thinking ?? false,
      supportsVision: model?.supports_vision ?? false,
      supportsToolCalling: model?.supports_tool_calling ?? true,
    }
  }

  /**
   * 检查执行模式是否可用
   *
   * DeerFlow InputMode: flash | thinking | pro | ultra
   *
   * - Flash: 始终可用
   * - Thinking/Pro: 需要 supports_thinking
   * - Ultra: 需要 supports_thinking + subagent_enabled
   */
  function isModeAvailable(
    mode: 'flash' | 'thinking' | 'pro' | 'ultra',
    modelName: string,
  ): boolean {
    const caps = getModelCapabilities(modelName)

    // Flash 模式始终可用
    if (mode === 'flash') return true

    // 其他模式需要 thinking 支持
    if (!caps.supportsThinking) return false

    // Ultra 模式还需要 subagent 支持
    if (mode === 'ultra' && !supportsSubagent.value) return false

    return true
  }

  // 自动加载
  onMounted(loadResources)

  // Race-condition fix: onMounted(loadResources) can fire before the Pinia
  // family store is populated (App.vue fetchMe()→fetchFamily() is async and
  // not awaited). In that case loadResources() bails out at the !familyId
  // check and never retries. Watch familyId so that when it eventually lands
  // we retry — but only if we haven't already loaded models.
  watch(familyId, (newId) => {
    if (newId && models.value.length === 0 && !loading.value) {
      loadResources()
    }
  })

  return {
    models,
    tenantConfig,
    loading,
    error,
    supportsThinking,
    supportsSubagent,
    supportsWebSearch,
    hasWebSearchMcp,
    webSearchAvailable,
    defaultModel,
    loadResources,
    getModelCapabilities,
    isModeAvailable,
  }
}

export type InputMode = 'flash' | 'thinking' | 'pro' | 'ultra'

/**
 * 执行模式配置
 *
 * DeerFlow 参考: frontend/src/components/workspace/input-box.tsx INPUT_MODE_CONFIGS
 */
export interface InputModeConfig {
  mode: InputMode
  thinking_enabled: boolean
  is_plan_mode: boolean
  subagent_enabled: boolean
  reasoning_effort: 'minimal' | 'low' | 'medium' | 'high'
  icon: string
  label: string
  description: string
}

export const INPUT_MODE_CONFIGS: Record<
  'flash' | 'thinking' | 'pro' | 'ultra',
  InputModeConfig
> = {
  flash: {
    mode: 'flash',
    thinking_enabled: false,
    is_plan_mode: false,
    subagent_enabled: false,
    reasoning_effort: 'minimal',
    icon: 'lucide:zap',
    label: '闪电',
    description: '快速响应，无深度思考',
  },
  thinking: {
    mode: 'thinking',
    thinking_enabled: true,
    is_plan_mode: false,
    subagent_enabled: false,
    reasoning_effort: 'low',
    icon: 'lucide:lightbulb',
    label: '思考',
    description: '启用思考链，逐步推理',
  },
  pro: {
    mode: 'pro',
    thinking_enabled: true,
    is_plan_mode: true,
    subagent_enabled: false,
    reasoning_effort: 'medium',
    icon: 'lucide:graduation-cap',
    label: '专业',
    description: '计划模式，自动拆解任务',
  },
  ultra: {
    mode: 'ultra',
    thinking_enabled: true,
    is_plan_mode: true,
    subagent_enabled: true,
    reasoning_effort: 'high',
    icon: 'lucide:rocket',
    label: '旗舰',
    description: '完整能力，子代理协作',
  },
}

/**
 * 根据模型能力解析最终可用模式
 *
 * DeerFlow 参考: input-box.tsx getResolvedMode()
 */
export function getResolvedMode(
  requestedMode: 'flash' | 'thinking' | 'pro' | 'ultra' | undefined,
  supportsThinking: boolean,
  supportsSubagent: boolean,
): 'flash' | 'thinking' | 'pro' | 'ultra' {
  // 不支持 thinking 的模型强制降级到 flash
  if (!supportsThinking && requestedMode !== 'flash') {
    return 'flash'
  }

  // Ultra 模式需要 subagent 支持
  if (requestedMode === 'ultra' && !supportsSubagent) {
    return 'pro' // 降级到 pro
  }

  // 默认模式
  return requestedMode ?? (supportsThinking ? 'pro' : 'flash')
}