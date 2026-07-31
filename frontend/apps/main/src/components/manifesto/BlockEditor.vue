<template>
  <div class="block-editor">
    <div v-for="(block, index) in blocks" :key="index" class="block-card">
      <div class="block-header">
        <span class="block-label">{{ t('manifesto.paragraph') }} {{ index + 1 }}</span>
        <div class="block-actions">
          <van-switch
            :model-value="trackableIndices.includes(index)"
            size="20px"
            @update:model-value="toggleTrackable(index, $event)"
          />
          <span class="trackable-label">{{ t('manifesto.trackable') }}</span>
          <van-icon
            v-if="blocks.length > 1"
            name="cross"
            class="delete-btn"
            @click="deleteBlock(index)"
          />
        </div>
      </div>
      <van-field
        :model-value="block"
        type="textarea"
        autosize
        :placeholder="t('manifesto.addBlock')"
        @update:model-value="updateBlock(index, $event)"
      />
    </div>
    <van-button type="primary" plain size="small" block @click="addBlock">
      + {{ t('manifesto.addBlock') }}
    </van-button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface BlockEditorValue {
  blocks: string[]
  trackableIndices: number[]
}

const props = defineProps<{
  modelValue: BlockEditorValue
}>()

const emit = defineEmits<{
  'update:modelValue': [value: BlockEditorValue]
}>()

const blocks = ref<string[]>([...props.modelValue.blocks])
const trackableIndices = ref<number[]>([...props.modelValue.trackableIndices])

watch(() => props.modelValue, (val) => {
  blocks.value = [...val.blocks]
  trackableIndices.value = [...val.trackableIndices]
}, { deep: true })

function emitUpdate() {
  emit('update:modelValue', {
    blocks: [...blocks.value],
    trackableIndices: [...trackableIndices.value],
  })
}

function updateBlock(index: number, value: string) {
  blocks.value[index] = value
  emitUpdate()
}

function addBlock() {
  blocks.value.push('')
  emitUpdate()
}

function deleteBlock(index: number) {
  if (blocks.value.length <= 1) return
  blocks.value.splice(index, 1)
  // Recalculate trackable indices
  trackableIndices.value = trackableIndices.value
    .filter(i => i !== index)
    .map(i => i > index ? i - 1 : i)
  emitUpdate()
}

function toggleTrackable(index: number, value: boolean) {
  if (value) {
    if (!trackableIndices.value.includes(index)) {
      trackableIndices.value.push(index)
    }
  } else {
    trackableIndices.value = trackableIndices.value.filter(i => i !== index)
  }
  emitUpdate()
}
</script>

<style scoped>
.block-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-card {
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: 8px;
  padding: 12px;
  background: var(--card-bg, #fff);
}

.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.block-label {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary, #0a0a0a);
}

.block-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.trackable-label {
  font-size: 12px;
  color: var(--text-secondary, #616161);
}

.delete-btn {
  cursor: pointer;
  color: var(--text-secondary, #616161);
  padding: 4px;
}
</style>
