<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'

const { t, locale } = useI18n()

const emit = defineEmits<{
  consult: []
}>()
</script>

<template>
  <div class="numina-agent-card" role="button" tabindex="0" @click="emit('consult')">
    <!-- Full-width featured card for 数鸣 agent - horizontal layout -->
    <div class="numina-card__inner">
      <!-- Left: AI brain icon (from nav bar) -->
      <div class="numina-card__icon">
        <AIBrainIcon :active="false" />
      </div>

      <!-- Right: Colorful name + description -->
      <div class="numina-card__content">
        <!-- Colorful name: 数 · 鸣 (zh) / numin~A~gent (en) -->
        <div class="numina-card__name">
          <template v-if="locale === 'zh-CN'">
            <span class="numina-char nc1">数</span>
            <span class="numina-char dot">·</span>
            <span class="numina-char nc2">鸣</span>
          </template>
          <template v-else>
            <span class="numina-char nc1">n</span>
            <span class="numina-char nc2">u</span>
            <span class="numina-char nc3">m</span>
            <span class="numina-char nc4">i</span>
            <span class="numina-char nc5">n</span>
            <span class="numina-char tilde">~</span>
            <span class="numina-char nc6">A</span>
            <span class="numina-char tilde">~</span>
            <span class="numina-char nc7">g</span>
            <span class="numina-char nc8">e</span>
            <span class="numina-char nc9">n</span>
            <span class="numina-char nc1">t</span>
          </template>
        </div>

        <!-- Description -->
        <div class="numina-card__desc">{{ t('aiHub.numinaAgentDesc') }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.numina-agent-card {
  /* Full-width card spanning 2 columns */
  grid-column: 1 / -1;
  border-radius: 12px;
  background: var(--card-bg);
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: rgba(1, 1, 32, 0.06) 0px 2px 8px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  overflow: hidden;
}

[data-theme='dark'] .numina-agent-card {
  border-color: rgba(255, 255, 255, 0.10);
  box-shadow: rgba(1, 1, 32, 0.3) 0px 2px 8px;
}

.numina-agent-card:active {
  transform: scale(0.98);
}

/* Horizontal layout: icon left, name/desc right */
.numina-card__inner {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 16px;
  gap: 16px;
}

/* Icon wrapper */
.numina-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.numina-card__icon :deep(.ai-button-wrapper) {
  transform: translateY(0);
}

.numina-card__icon :deep(.ai-button-3d) {
  width: 48px;
  height: 48px;
}

/* Right content area */
.numina-card__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

/* Colorful name with rainbow colors (adapted from LoginPage subtitle) */
.numina-card__name {
  font-family: 'ZCOOL KuaiLe', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 22px;
  letter-spacing: 0.08em;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.numina-char {
  display: inline-block;
  animation: numinaFloat 3s ease-in-out infinite;
}

.numina-char:nth-child(odd) {
  animation-direction: alternate;
}

@keyframes numinaFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}

/* Rainbow colors — warm to cool cycle (matching LoginPage) */
.nc1 { color: #ff6b6b; animation-delay: 0s; }
.nc2 { color: #ff9f43; animation-delay: 0.1s; }
.nc3 { color: #ffd93d; animation-delay: 0.15s; }
.nc4 { color: #6bcb77; animation-delay: 0.2s; }
.nc5 { color: #4ecdc4; animation-delay: 0.25s; }
.nc6 { color: #74b9ff; animation-delay: 0.3s; }
.nc7 { color: #a29bfe; animation-delay: 0.35s; }
.nc8 { color: #fd79a8; animation-delay: 0.4s; }
.nc9 { color: #fdcb6e; animation-delay: 0.45s; }

.dot {
  color: rgba(0, 0, 0, 0.4);
  animation-delay: 0.05s;
}

[data-theme='dark'] .dot {
  color: rgba(255, 255, 255, 0.5);
}

.tilde {
  color: #bdbbff;
  animation-delay: 0.28s;
}

@media (prefers-reduced-motion: reduce) {
  .numina-char {
    animation: none;
  }
}

.numina-card__desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}
</style>