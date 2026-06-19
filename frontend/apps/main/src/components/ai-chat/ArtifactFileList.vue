<script setup lang="ts">
/**
 * DeerFlow ArtifactFileList 组件
 *
 * 参考: frontend/src/components/workspace/artifacts/artifact-file-list.tsx
 *
 * 功能:
 * - 渲染文件列表（卡片式）
 * - 文件类型图标
 * - 点击触发全屏预览
 * - Skill 文件安装按钮
 */
import { useI18n } from 'vue-i18n'
import { Button } from 'vant'
import IIcon from '@/components/IIcon.vue'
import { getFileName, getFileIcon, isSkillFile } from '@/utils/ai-chat/fileType'
import { artifactDownloadUrl } from '@/utils/ai-chat/artifactUrl'
import type { Artifact } from '@/types/agent-stream'

const { t } = useI18n()

const props = defineProps<{
  artifacts: Artifact[]
  sessionId: string
}>()

const emit = defineEmits<{
  select: [artifact: Artifact]
}>()

// 文件卡片点击 → 打开预览
function handleClick(artifact: Artifact) {
  emit('select', artifact)
}

// Skill 文件安装（DeerFlow 特殊处理）
function handleInstallSkill(filepath: string) {
  // TODO: 实现 skill installation
  console.log('Install skill:', filepath)
}

// 下载链接
function getDownloadUrl(artifact: Artifact): string {
  return artifactDownloadUrl(artifact.path || artifact.id || '', props.sessionId)
}

// 打开下载链接（Vue template 中 window 需要通过函数访问）
function openDownloadUrl(artifact: Artifact) {
  window.open(getDownloadUrl(artifact), '_blank')
}
</script>

<template>
  <div class="artifact-file-list">
    <div
      v-for="artifact in artifacts"
      :key="artifact.id || artifact.path"
      class="artifact-card"
      role="button"
      tabindex="0"
      @click="handleClick(artifact)"
      @keydown.enter="handleClick(artifact)"
    >
      <div class="artifact-card-body">
        <!-- 文件图标 -->
        <IIcon :icon="getFileIcon(artifact.path || '')" class="file-icon" />

        <div class="artifact-card-info">
          <!-- 文件标题 -->
          <span class="file-name">{{ getFileName(artifact.path || '') }}</span>
          <!-- 文件描述 -->
          <span class="file-kind">{{ artifact.kind || t('aiArtifact.defaultKind') }}</span>
        </div>

        <!-- 操作按钮 -->
        <div class="card-actions" @click.stop>
          <Button
            v-if="isSkillFile(artifact.path || '')"
            size="small"
            type="primary"
            @click.stop="handleInstallSkill(artifact.path || '')"
          >
            {{ t('aiArtifact.install') }}
          </Button>
          <Button
            size="small"
            plain
            @click.stop="openDownloadUrl(artifact)"
          >
            {{ t('aiArtifact.download') }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.artifact-file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}

.artifact-card {
  background: var(--card-bg);
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: background 0.2s;
}

.artifact-card:hover,
.artifact-card:focus-visible {
  background: rgba(0, 0, 0, 0.02);
  outline: none;
}

.artifact-card-body {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.file-icon {
  width: 24px;
  height: 24px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.artifact-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-kind {
  font-size: 12px;
  color: var(--text-secondary);
}

.card-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 375px */
@media (max-width: 375px) {
  .file-name {
    font-size: 13px;
  }

  .file-kind {
    font-size: 11px;
  }
}
</style>