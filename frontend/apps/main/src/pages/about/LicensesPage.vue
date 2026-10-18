<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { ossComponents } from './data/licenses'

const { t } = useI18n()
</script>

<template>
  <ContentPage :title="t('settings.openSourceLicenses')">
    <p class="licenses-intro">{{ t('settings.licensedUnder') }}</p>
    <div class="licenses-list">
      <div v-for="comp in ossComponents" :key="comp.name" class="license-item">
        <a :href="comp.url" target="_blank" rel="noopener" class="license-name">{{ comp.name }}</a>
        <span class="license-badge">{{ comp.license }}</span>
      </div>
    </div>
  </ContentPage>
</template>

<style scoped>
.licenses-intro {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 16px;
  line-height: 1.6;
}

.license-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--van-border-color);
}

.license-item:last-child {
  border-bottom: none;
}

.license-name {
  font-size: 14px;
  color: var(--van-primary-color);
  text-decoration: none;
}

.license-badge {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--card-bg);
  padding: 2px 8px;
  border-radius: 4px;
}
</style>
