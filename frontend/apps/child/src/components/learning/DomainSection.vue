<template>
  <section class="domain-section" :data-domain="domain">
    <button
      type="button"
      class="domain-section__header"
      :aria-expanded="expanded"
      :aria-label="`${domainLabel}，${t(expanded ? 'learning.domainSection.collapseSection' : 'learning.domainSection.expandSection')}`"
      :class="{ 'domain-section__header--instant': instant }"
      @click="$emit('toggle')"
    >
      <span class="domain-section__label">{{ domainLabel }}</span>
      <span
        v-if="pathCount && pathCount > 0 && !expanded"
        class="domain-section__path-badge"
      >{{ t('learning.recommendPath.hiddenTopics', { count: pathCount }) }}</span>
      <span class="domain-section__progress">
        {{ t('learning.cluster.progress', { mastered: masteredCount, total: totalCount }) }}
      </span>
      <span class="domain-section__chevron" :class="{ 'domain-section__chevron--expanded': expanded }" />
    </button>

    <div class="domain-section__collapse-wrapper" :inert="!expanded">
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
  /** Programmatic expand (frontier/bridge): skip the height transition so
   *  `scrollIntoView` measures final geometry instead of an animating row. */
  instant?: boolean
  /** Number of recommendation path topics hidden inside this collapsed section. */
  pathCount?: number
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

.domain-section__path-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--radius-pill);
  background: var(--color-path-badge-bg, var(--color-brand-ochre));
  color: var(--color-path-badge-text, var(--color-on-dark));
  font-family: Inter, sans-serif;
  font-size: 11px;
  font-weight: 600;
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

/* Programmatic expand (frontier/bridge auto-expand): no transition, so the
   section is at final height when the scroll measures it. */
.domain-section__header--instant + .domain-section__collapse-wrapper {
  transition: none;
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
