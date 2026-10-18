<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { changelog } from './data/changelog'

const { t } = useI18n()
</script>

<template>
  <ContentPage :title="t('settings.changelog')">
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
  margin-bottom: 20px;
}

.changelog-version {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.version-tag {
  font-size: 14px;
  font-weight: 600;
  color: var(--van-primary-color);
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
