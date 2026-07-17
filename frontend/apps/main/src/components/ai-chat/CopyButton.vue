<script setup lang="ts">
/**
 * CopyButton — 可复用的复制逻辑包装组件
 *
 * 只负责「调用 copyToClipboard + toast 反馈 + 暴露 copied 瞬时状态」，
 * 不渲染固定按钮/图标/样式，由默认 slot 承载调用方自己的按钮。
 * 这样不同场景（消息工具条 action-btn、代码块 copy-btn、引用源按钮）
 * 各自保持视觉一致性，仅共享复制逻辑。
 *
 * Slot props:
 *   - copy: () => void      触发复制（绑定到调用方按钮的 @click）
 *   - copied: boolean       复制成功后的瞬时状态（用于切换 ✓ 图标，约 1.5s）
 *
 * 用法示例：
 *   <CopyButton :content="text" v-slot="{ copy, copied }">
 *     <button class="my-btn" @click="copy">
 *       <svg v-if="copied" .../><svg v-else .../>
 *     </button>
 *   </CopyButton>
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { copyToClipboard } from '@/utils/ai-chat/tableUtils'

const props = withDefaults(defineProps<{
  content: string
  /** 成功 toast 文案 key，默认 aiChat.copiedSuccess */
  successKey?: string
  /** 失败 toast 文案 key，默认 aiChat.copyFailed */
  failKey?: string
  /** copied 瞬时状态持续时长（ms），默认 1500 */
  copiedDuration?: number
}>(), {
  successKey: 'aiChat.copiedSuccess',
  failKey: 'aiChat.copyFailed',
  copiedDuration: 1500,
})

const { t } = useI18n()
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

async function copy() {
  const ok = await copyToClipboard(props.content)
  if (ok) {
    showSuccessToast(t(props.successKey))
    copied.value = true
    if (copiedTimer) clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => {
      copied.value = false
      copiedTimer = null
    }, props.copiedDuration)
  } else {
    showFailToast(t(props.failKey))
  }
}
</script>

<template>
  <slot :copy="copy" :copied="copied" />
</template>
