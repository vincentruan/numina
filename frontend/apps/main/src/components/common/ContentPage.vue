<script setup lang="ts">
import PageHeader from '@/components/common/PageHeader.vue'

defineProps<{
  title: string
  lastUpdated?: string
}>()
</script>

<template>
  <div class="content-page">
    <PageHeader :title="title" />
    <div class="content-body">
      <p v-if="lastUpdated" class="content-updated">
        {{ lastUpdated }}
      </p>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.content-page {
  min-height: 100vh;
}

.content-body {
  padding: 16px 20px 40px;
  overflow-y: auto;
}

.content-updated {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

:deep(h2) {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 24px 0 12px;
}

:deep(h3) {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 20px 0 8px;
}

:deep(p) {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  margin: 0 0 12px;
}

:deep(ul),
:deep(ol) {
  padding-left: 20px;
  margin: 0 0 12px;
}

:deep(li) {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  margin-bottom: 4px;
}

:deep(a) {
  color: var(--van-primary-color);
  text-decoration: none;
}

:deep(strong) {
  font-weight: 600;
}
</style>
