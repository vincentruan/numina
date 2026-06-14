<script setup lang="ts">
/**
 * DeerFlow ArtifactFileList 组件
 *
 * 参考: frontend/src/components/workspace/artifacts/artifact-file-list.tsx
 *
 * 功能:
 * - 渲染文件列表（Card 组件）
 * - 文件类型图标
 * - 点击触发全屏预览
 * - Skill 文件安装按钮
 */
import { Card, Button } from 'vant'
import { useI18n } from 'vue-i18n'
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
</script>

<template>
  <div class="artifact-file-list">
    <Card
      v-for="artifact in artifacts"
      :key="artifact.id || artifact.path"
      class="artifact-card"
      clickable
      @click="handleClick(artifact)"
    >
      <!-- 文件图标 -->
      <template #icon>
        <SvgIcon :name="getFileIcon(artifact.path || '')" class="file-icon" />
      </template>

      <!-- 文件标题 -->
      <template #title>
        <span class="file-name">{{ getFileName(artifact.path || '') }}</span>
      </template>

      <!-- 文件描述 -->
      <template #desc>
        <span class="file-kind">{{ artifact.kind || t('aiArtifact.defaultKind') }}</span>
      </template>

      <!-- 操作按钮 -->
      <template #footer>
        <div class="card-actions">
          <!-- Skill 文件：安装按钮 -->
          <Button
            v-if="isSkillFile(artifact.path || '')"
            size="small"
            type="primary"
            @click.stop="handleInstallSkill(artifact.path || '')"
          >
            {{ t('aiArtifact.install') }}
          </Button>

          <!-- 下载按钮 -->
          <Button
            size="small"
            plain
            @click.stop="window.open(getDownloadUrl(artifact), '_blank')"
          >
            {{ t('aiArtifact.download') }}
          </Button>
        </div>
      </template>
    </Card>
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
}

.file-icon {
  width: 24px;
  height: 24px;
  color: var(--text-secondary);
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.file-kind {
  font-size: 12px;
  color: var(--text-secondary);
}

.card-actions {
  display: flex;
  gap: 8px;
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