<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { changelog } from './data/changelog'

const { t } = useI18n()
</script>

<template>
  <ContentPage :title="t('settings.changelog')" back-to="/settings/about">
    <div v-for="release in changelog" :key="release.version" class="changelog-release">
      <div class="changelog-version">
        <span class="version-tag">v{{ release.version }}</span>
        <span class="version-date">{{ release.date }}</span>
      </div>
      <ul class="changelog-list">
        <li v-for="(changeKey, idx) in release.changes" :key="idx">{{ t(changeKey) }}</li>
      </ul>
    </div>
  </ContentPage>
</template>

<style scoped>
.changelog-release {
  position: relative;
  padding-left: 16px;
  margin-bottom: 24px;
  border-left: 2px solid var(--van-border-color);
}

.changelog-release:last-child {
  border-left-color: transparent;
}

.changelog-version {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.version-tag {
  display: inline-block;
  font-size: 15px;
  font-weight: 700;
  color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 10%, transparent);
  padding: 2px 10px;
  border-radius: 6px;
}

.version-date {
  font-size: 12px;
  color: var(--text-secondary);
}

.changelog-list {
  margin: 0;
  padding-left: 20px;
  list-style: disc;
}

.changelog-list li {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.8;
}
</style>
