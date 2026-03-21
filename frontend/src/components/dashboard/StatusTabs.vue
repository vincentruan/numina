<template>
  <van-tabs v-model:active="activeTab" shrink sticky @change="onChange">
    <van-tab title="全部" name="all" />
    <van-tab title="使用中" name="in_use" />
    <van-tab title="闲置" name="idle" />
    <van-tab title="已出售" name="sold" />
    <van-tab title="已报废" name="retired" />
  </van-tabs>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const activeTab = ref<string>(props.modelValue || 'all')

watch(() => props.modelValue, (val) => {
  activeTab.value = val || 'all'
})

function onChange(name: string | number) {
  const value = name === 'all' ? null : String(name)
  emit('update:modelValue', value)
}
</script>

<style scoped>
:deep(.van-tabs__nav) {
  background: #fff;
}
:deep(.van-tab) {
  font-size: 13px;
}
</style>