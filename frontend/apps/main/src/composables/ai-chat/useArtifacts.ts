/**
 * DeerFlow Artifacts 状态管理 Composable
 *
 * 参考: frontend/src/components/workspace/artifacts/context.tsx
 *
 * 职责:
 * - 管理 artifacts 字典 (Record<string, Artifact>)
 * - 管理当前选中的 artifact (selectedArtifact)
 * - 管理预览弹出层状态 (open)
 * - 提供 select/deselect/autoSelect 方法
 */

import { ref, computed, readonly } from 'vue'
import type { Artifact } from '@/types/agent-stream'

// 状态
const artifacts = ref<Record<string, Artifact>>({})
const selectedArtifact = ref<Artifact | null>(null)
const open = ref(false)

/**
 * Artifacts Context Composable
 */
export function useArtifacts() {
  /**
   * 设置 artifacts（从 tool call result 或 SSE 事件提取）
   */
  function setArtifacts(newArtifacts: Artifact[]) {
    const dict: Record<string, Artifact> = {}
    for (const artifact of newArtifacts) {
      // 使用 artifact.id 或 path 作为 key
      const key = artifact.id || artifact.path || ''
      if (key) {
        dict[key] = artifact
      }
    }
    artifacts.value = dict
  }

  /**
   * 添加单个 artifact
   */
  function addArtifact(artifact: Artifact) {
    const key = artifact.id || artifact.path || ''
    if (key) {
      artifacts.value[key] = artifact
    }
  }

  /**
   * 选择 artifact 并打开预览
   */
  function select(artifact: Artifact) {
    selectedArtifact.value = artifact
    open.value = true
  }

  /**
   * 通过 filepath 选择 artifact
   */
  function selectByPath(filepath: string) {
    const artifact = artifacts.value[filepath]
    if (artifact) {
      select(artifact)
    }
  }

  /**
   * 取消选择并关闭预览
   */
  function deselect() {
    selectedArtifact.value = null
    open.value = false
  }

  /**
   * 自动选择最新 artifact（用于 present_files tool）
   */
  function autoSelect() {
    const keys = Object.keys(artifacts.value)
    if (keys.length > 0) {
      const latestKey = keys[keys.length - 1]
      select(artifacts.value[latestKey])
    }
  }

  /**
   * 自动打开预览（配合 autoSelect）
   */
  function autoOpen() {
    if (!open.value && Object.keys(artifacts.value).length > 0) {
      autoSelect()
    }
  }

  /**
   * 设置弹出层状态
   */
  function setOpen(isOpen: boolean) {
    open.value = isOpen
    if (!isOpen) {
      selectedArtifact.value = null
    }
  }

  /**
   * 清除所有 artifacts（session 结束时）
   */
  function clearArtifacts() {
    artifacts.value = {}
    selectedArtifact.value = null
    open.value = false
  }

  return {
    artifacts: readonly(artifacts),
    artifactList: computed(() => Object.values(artifacts.value)),
    selectedArtifact: readonly(selectedArtifact),
    open: readonly(open),
    setArtifacts,
    addArtifact,
    select,
    selectByPath,
    deselect,
    autoSelect,
    autoOpen,
    setOpen,
    clearArtifacts,
  }
}

/**
 * 加载 Artifact 内容
 *
 * 参考: frontend/src/core/artifacts/loader.ts loadArtifactContent()
 */
export async function loadArtifactContent(filepath: string, sessionId: string): Promise<string> {
  const encodedPath = encodeURIComponent(filepath)
  const url = `/api/sessions/${sessionId}/artifacts/${encodedPath}`

  const response = await fetch(url, {
    headers: {
      'X-Family-Id': localStorage.getItem('currentFamilyId') || '',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to load artifact: ${response.statusText}`)
  }

  return response.text()
}

/**
 * useArtifactContent Hook（带缓存）
 *
 * 参考: frontend/src/core/artifacts/hooks.ts useArtifactContent()
 *
 * 使用 Vue 响应式缓存，避免重复请求
 */
export function useArtifactContent(filepath: string, sessionId: string) {
  const content = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 缓存 key
  const cacheKey = `${sessionId}:${filepath}`

  // 全局缓存（5分钟 staleTime）
  const contentCache = new Map<string, { content: string; timestamp: number }>()
  const STALE_TIME = 5 * 60 * 1000 // 5 minutes

  async function load() {
    // 检查缓存
    const cached = contentCache.get(cacheKey)
    if (cached && Date.now() - cached.timestamp < STALE_TIME) {
      content.value = cached.content
      return
    }

    loading.value = true
    error.value = null

    try {
      const result = await loadArtifactContent(filepath, sessionId)
      content.value = result
      contentCache.set(cacheKey, { content: result, timestamp: Date.now() })
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  return {
    content,
    loading,
    error,
    load,
  }
}