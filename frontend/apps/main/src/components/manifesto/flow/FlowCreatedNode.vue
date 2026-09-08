<template>
  <div :class="[baseClass, dimmed ? nodeClasses.dimmed : '']">
    <div class="flow-node__icon">
      <van-icon :name="changeType === 'initial' ? 'certificate' : 'replay'" />
    </div>
    <div class="flow-created__content">
      <div class="flow-created__title">
        <template v-if="changeType === 'initial'">
          {{ t('manifesto.flow.created') }}
        </template>
        <template v-else>
          {{ t('manifesto.updated') }}
          <span class="flow-created__version">{{ t('manifesto.flow.versionLabel', { n: versionNumber }) }}</span>
          <span class="flow-created__change-type">· {{ changeTypeLabel }}</span>
        </template>
      </div>
      <div v-if="creatorName" class="flow-created__meta">
        <span class="flow-created__role">{{ changeType === 'initial' ? t('manifesto.flow.createdBy') : t('manifesto.flow.updatedBy') }}</span>
        <span>{{ creatorName }}</span>
      </div>
      <div v-if="createdAt" class="flow-created__date">{{ createdAt }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Position, type NodeProps } from '@vue-flow/core'
import { nodeClasses, NODE_WIDTH } from './flowNodeStyles'

const { t } = useI18n()

const props = defineProps<NodeProps>()

const baseClass = computed(() => nodeClasses.created)
const dimmed = computed(() => props.data?.dimmed === true)
const changeType = computed<string>(() => props.data?.changeType ?? 'initial')
const versionNumber = computed<number>(() => props.data?.versionNumber ?? 1)
const creatorName = computed<string>(() => props.data?.creatorName ?? '')
const createdAt = computed<string>(() => props.data?.createdAt ?? '')
const changeTypeLabel = computed<string>(() => {
  switch (changeType.value) {
    case 'minor': return t('manifesto.flow.changeTypeMinor')
    case 'major': return t('manifesto.flow.changeTypeMajor')
    default: return t('manifesto.flow.changeTypeInitial')
  }
})

defineExpose({ position: Position.Top })
</script>

<style scoped>
.flow-node--created {
  width: v-bind(NODE_WIDTH);
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--card-bg, #f5f5ff);
  border: 1.5px solid var(--card-bg, #f5f5ff);
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 14px;
  color: var(--text-secondary, #616161);
}

.flow-node--dimmed {
  opacity: 0.5;
}

.flow-node__icon {
  font-size: 18px;
  flex-shrink: 0;
}

.flow-node__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.flow-created__content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.flow-created__title {
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.flow-created__version {
  font-size: 12px;
  color: var(--van-primary-color, #646cff);
  background: rgba(100, 108, 255, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
}

.flow-created__change-type {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary, #616161);
}

.flow-created__meta {
  font-size: 12px;
  display: flex;
  gap: 4px;
}

.flow-created__role {
  color: var(--text-secondary, #616161);
}

.flow-created__date {
  font-size: 11px;
  color: var(--text-secondary, #616161);
}
</style>
