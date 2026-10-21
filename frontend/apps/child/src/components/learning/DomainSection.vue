<template>
  <section class="domain-section" :data-domain="domain">
    <button
      type="button"
      class="domain-section__header"
      :aria-expanded="expanded"
      :aria-label="expanded ? t('learning.domainSection.collapseSection') : t('learning.domainSection.expandSection')"
      @click="$emit('toggle')"
    >
      <span class="domain-section__label">{{ domainLabel }}</span>
      <span class="domain-section__progress">
        {{ t('learning.domainSection.progress', { mastered: masteredCount, total: totalCount }) }}
      </span>
      <span class="domain-section__chevron" :class="{ 'domain-section__chevron--expanded': expanded }" />
    </button>

    <div class="domain-section__collapse-wrapper">
      <div class="domain-section__content">
        <slot />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
defineOptions({ name: 'DomainSection' })

import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  domain: string
  domainLabel: string
  masteredCount: number
  totalCount: number
  expanded: boolean
}>()

defineEmits<{
  toggle: []
}>()
</script>

<style scoped>
.domain-section {
  display: flex;
  flex-direction: column;
}

.domain-section__header {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 8px 12px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s;
  text-align: left;
  width: 100%;
  font-family: inherit;
}

.domain-section__header:active {
  background: var(--color-hairline);
}

/* When expanded, give the header a slightly different look */
.domain-section__header[aria-expanded="true"] {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  border-bottom-color: transparent;
}

.domain-section__label {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  flex-shrink: 0;
}

.domain-section__progress {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 400;
  color: var(--color-body);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.domain-section__chevron {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border-right: 2px solid var(--color-body);
  border-bottom: 2px solid var(--color-body);
  transform: rotate(45deg) scale(0.7);
  transition: transform 0.3s ease;
  margin-left: auto;
}

.domain-section__chevron--expanded {
  transform: rotate(-135deg) scale(0.7);
}

/* ── Collapse animation via grid-template-rows ── */

.domain-section__collapse-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease;
}

.domain-section__header[aria-expanded="true"] + .domain-section__collapse-wrapper {
  grid-template-rows: 1fr;
}

.domain-section__content {
  overflow: hidden;
  min-height: 0;
}

/* ── Reduced motion ── */

@media (prefers-reduced-motion: reduce) {
  .domain-section__collapse-wrapper,
  .domain-section__chevron {
    transition: none;
  }
}
</style>
