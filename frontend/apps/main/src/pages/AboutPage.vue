<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import { showToast } from 'vant'

const { t } = useI18n()

// App version — injected at build time from package.json via Vite define
const APP_VERSION = __APP_VERSION__
const PROJECT_URL = 'https://github.com/vincentruan/numina'

// Changelog data
interface ReleaseNote {
  version: string
  date: string
  changes: string[]
}

const changelog = ref<ReleaseNote[]>([
  {
    version: '1.0.0',
    date: '2026-10-16',
    changes: [
      t('settings.changelogV1_1'),
      t('settings.changelogV1_2'),
      t('settings.changelogV1_3'),
      t('settings.changelogV1_4'),
      t('settings.changelogV1_5'),
      t('settings.changelogV1_6'),
      t('settings.changelogV1_7'),
    ],
  },
])

const showChangelog = ref(false)
const showOpenSource = ref(false)

// Open source components declaration
interface OSSComponent {
  name: string
  license: string
  url: string
}

const ossComponents = ref<OSSComponent[]>([
  { name: 'Vue 3', license: 'MIT', url: 'https://vuejs.org' },
  { name: 'Vant 4', license: 'MIT', url: 'https://vant-ui.github.io/vant' },
  { name: 'FastAPI', license: 'MIT', url: 'https://fastapi.tiangolo.com' },
  { name: 'SQLAlchemy', license: 'MIT', url: 'https://www.sqlalchemy.org' },
  { name: 'DeerFlow', license: 'MIT', url: 'https://github.com/bytedance/deer-flow' },
  { name: 'LangChain', license: 'MIT', url: 'https://www.langchain.com' },
  { name: 'LangGraph', license: 'MIT', url: 'https://github.com/langchain-ai/langgraph' },
  { name: 'ECharts', license: 'Apache-2.0', url: 'https://echarts.apache.org' },
  { name: 'DuckDB', license: 'MIT', url: 'https://duckdb.org' },
  { name: 'Vite', license: 'MIT', url: 'https://vitejs.dev' },
  { name: 'Pinia', license: 'MIT', url: 'https://pinia.vuejs.org' },
  { name: 'vue-i18n', license: 'MIT', url: 'https://vue-i18n.intlify.dev' },
  { name: 'Tavily', license: 'MIT', url: 'https://tavily.com' },
  { name: 'e2b', license: 'Apache-2.0', url: 'https://e2b.dev' },
])

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
        @click="showChangelog = true"
      />
      <van-cell
        :title="t('settings.termsOfService')"
        icon="shield-o"
        is-link
        @click="openProjectUrl"
      />
      <van-cell
        :title="t('settings.privacyPolicy')"
        icon="lock"
        is-link
        @click="openProjectUrl"
      />
      <van-cell
        :title="t('settings.openSourceLicenses')"
        icon="certificate"
        is-link
        @click="showOpenSource = true"
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

    <!-- Changelog Popup -->
    <van-popup v-model:show="showChangelog" round position="bottom" :style="{ maxHeight: '70vh' }">
      <div class="changelog-popup">
        <div class="changelog-header">
          <h3>{{ t('settings.changelog') }}</h3>
        </div>
        <div class="changelog-body">
          <div v-for="release in changelog" :key="release.version" class="changelog-release">
            <div class="changelog-version">
              <span class="version-tag">v{{ release.version }}</span>
              <span class="version-date">{{ release.date }}</span>
            </div>
            <ul class="changelog-list">
              <li v-for="(change, idx) in release.changes" :key="idx">{{ change }}</li>
            </ul>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- Open Source Popup -->
    <van-popup v-model:show="showOpenSource" round position="bottom" :style="{ maxHeight: '70vh' }">
      <div class="oss-popup">
        <div class="oss-header">
          <h3>{{ t('settings.openSourceLicenses') }}</h3>
        </div>
        <div class="oss-body">
          <div v-for="comp in ossComponents" :key="comp.name" class="oss-item">
            <a :href="comp.url" target="_blank" class="oss-name">{{ comp.name }}</a>
            <span class="oss-license">{{ comp.license }}</span>
          </div>
        </div>
      </div>
    </van-popup>
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

/* Changelog popup */
.changelog-popup,
.oss-popup {
  max-height: 70vh;
  display: flex;
  flex-direction: column;
}

.changelog-header,
.oss-header {
  padding: 16px;
  border-bottom: 1px solid var(--van-border-color);
  flex-shrink: 0;
}

.changelog-header h3,
.oss-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.changelog-body,
.oss-body {
  overflow-y: auto;
  padding: 16px;
  flex: 1;
}

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

/* OSS popup */
.oss-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--van-border-color);
}

.oss-item:last-child {
  border-bottom: none;
}

.oss-name {
  font-size: 14px;
  color: var(--van-primary-color);
  text-decoration: none;
}

.oss-name:active {
  opacity: 0.6;
}

.oss-license {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--van-background);
  padding: 2px 8px;
  border-radius: 4px;
}
</style>
