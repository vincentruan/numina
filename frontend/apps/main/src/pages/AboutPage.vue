<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import { showToast } from 'vant'

const { t } = useI18n()

// App version — injected at build time from package.json via Vite define
const APP_VERSION = __APP_VERSION__
const PROJECT_URL = 'https://github.com/vincentruan/numina'

function openProjectUrl() {
  window.open(PROJECT_URL, '_blank')
}

function copyVersion() {
  navigator.clipboard.writeText(APP_VERSION)
  showToast(t('common.copied'))
}
</script>

<template>
  <div class="about-page">
    <PageHeader :title="t('settings.aboutNumina')" />

    <!-- App Info Card -->
    <div class="about-header">
      <div class="about-logo">
        <img src="/favicon.svg" alt="Numina" class="about-logo-img" />
      </div>
      <h2 class="about-name">Numina</h2>
      <p class="about-desc">{{ t('settings.aboutDescription') }}</p>
      <p class="about-version" @click="copyVersion">
        {{ t('settings.currentVersion') }}: v{{ APP_VERSION }}
      </p>
    </div>

    <!-- Menu -->
    <van-cell-group inset class="section">
      <van-cell
        :title="t('settings.changelog')"
        icon="notes-o"
        is-link
        to="/settings/about/changelog"
      />
      <van-cell
        :title="t('settings.termsOfService')"
        icon="shield-o"
        is-link
        to="/settings/about/terms"
      />
      <van-cell
        :title="t('settings.privacyPolicy')"
        icon="lock"
        is-link
        to="/settings/about/privacy"
      />
      <van-cell
        :title="t('settings.openSourceLicenses')"
        icon="certificate"
        is-link
        to="/settings/about/licenses"
      />
      <van-cell
        :title="t('settings.projectHomepage')"
        icon="link-o"
        is-link
        @click="openProjectUrl"
      />
    </van-cell-group>

    <!-- Footer -->
    <div class="about-footer">
      <p>{{ t('settings.copyright') }}</p>
      <p>{{ t('settings.licensedUnder') }}</p>
    </div>
  </div>
</template>

<style scoped>
.about-page {
  min-height: 100vh;
  padding-bottom: 40px;
}

.about-header {
  text-align: center;
  padding: 24px 16px 32px;
}

.about-logo {
  margin-bottom: 12px;
}

.about-logo-img {
  width: 64px;
  height: 64px;
}

.about-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.about-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.about-version {
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.about-version:active {
  opacity: 0.6;
}

.section {
  margin-bottom: 16px;
}

.about-footer {
  text-align: center;
  padding: 32px 16px 16px;
  font-size: 12px;
  color: var(--text-secondary);
  opacity: 0.7;
}

.about-footer p {
  margin: 2px 0;
}
</style>
