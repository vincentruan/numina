<template>
  <div class="manifesto-template-select-page">
    <van-nav-bar
      :title="t('manifesto.selectTemplate')"
      left-arrow
      @click-left="router.back()"
    />
    <div class="template-grid">
      <div
        v-for="tmpl in sortedTemplates"
        :key="tmpl.id"
        class="template-card"
        :class="[`template-card--${tmpl.lang}`, { selected: state.selectedTemplateId === tmpl.id }]"
        @click="selectTemplate(tmpl.id)"
      >
        <div class="template-preview">
          <!-- Classic: certificate-style preview -->
          <template v-if="tmpl.nameKey === 'manifesto.template.classic'">
            <div class="preview-classic">
              <div class="preview-classic__double-border">
                <div class="preview-classic__emblem">⚜</div>
                <div class="preview-classic__title">{{ t(tmpl.nameKey) }}</div>
                <div class="preview-classic__lines">
                  <div class="preview-classic__line" />
                  <div class="preview-classic__line short" />
                </div>
              </div>
            </div>
          </template>
          <!-- Modern: clean-style preview -->
          <template v-else>
            <div class="preview-modern">
              <div class="preview-modern__header">
                <div class="preview-modern__accent" />
                <div class="preview-modern__title">{{ t(tmpl.nameKey) }}</div>
              </div>
              <div class="preview-modern__lines">
                <div class="preview-modern__line" />
                <div class="preview-modern__line short" />
              </div>
            </div>
          </template>
        </div>
        <div class="template-name">{{ t(tmpl.nameKey) }}</div>
        <div class="template-desc">{{ tmpl.nameKey === 'manifesto.template.classic' ? t('manifesto.template.classicDesc') : t('manifesto.template.modernDesc') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getTemplatesSorted } from '@/components/manifesto/templates/templateRegistry'
import { useManifestoWizard } from '@/composables/useManifestoWizard'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const { state } = useManifestoWizard()

const ownerLang = computed(() => {
  const lang = authStore.user?.language ?? 'zh-CN'
  return lang.startsWith('en') ? 'en' : 'zh'
})

// Deduplicate templates by base name — show one card per template type,
// preferring the owner's language variant.
const sortedTemplates = computed(() => {
  const all = getTemplatesSorted(ownerLang.value)
  const seen = new Set<string>()
  return all.filter((tmpl) => {
    // Group by the nameKey — same visual template shares the same nameKey
    if (seen.has(tmpl.nameKey)) return false
    seen.add(tmpl.nameKey)
    return true
  })
})

function selectTemplate(id: string) {
  state.value.selectedTemplateId = id
  router.push('/manifesto/edit')
}
</script>

<style scoped>
.manifesto-template-select-page {
  min-height: 100vh;
  background: var(--bg-primary, #fff);
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  padding: 16px;
}

.template-card {
  border: 2px solid var(--color-border, #dcdfe6);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  background: var(--card-bg, #fff);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.template-card:active {
  transform: scale(0.98);
}

.template-card.selected {
  border-color: var(--van-primary-color, #1989fa);
  box-shadow: 0 0 0 2px rgba(25, 137, 250, 0.15);
}

.template-preview {
  height: 140px;
  overflow: hidden;
}

/* ── Classic preview: certificate with double border + emblem ── */
.preview-classic {
  height: 100%;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #fdf6e3, #f5e6c8);
}

.preview-classic__double-border {
  width: calc(100% - 12px);
  height: calc(100% - 12px);
  border: 2px solid #c9a84c;
  border-radius: 4px;
  padding: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
}

.preview-classic__double-border::before {
  content: '';
  position: absolute;
  inset: 3px;
  border: 1px solid #c9a84c;
  border-radius: 2px;
  pointer-events: none;
}

.preview-classic__emblem {
  font-size: 18px;
  color: #c9a84c;
  line-height: 1;
  margin-bottom: 4px;
}

.preview-classic__title {
  font-family: 'Noto Serif SC', 'Times New Roman', serif;
  font-size: 12px;
  font-weight: 700;
  color: #5a4a2a;
  text-align: center;
  margin-bottom: 6px;
}

.preview-classic__lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 70%;
}

.preview-classic__line {
  height: 3px;
  background: #c9a84c;
  opacity: 0.4;
  border-radius: 2px;
}

.preview-classic__line.short {
  width: 60%;
  align-self: center;
}

/* ── Modern preview: clean with accent bar ── */
.preview-modern {
  height: 100%;
  padding: 10px;
  display: flex;
  flex-direction: column;
  background: linear-gradient(145deg, #f0f4ff, #e8edf8);
}

.preview-modern__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.preview-modern__accent {
  height: 3px;
  width: 40%;
  background: var(--van-primary-color, #1989fa);
  border-radius: 2px;
}

.preview-modern__title {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
}

.preview-modern__lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 0 4px;
}

.preview-modern__line {
  height: 3px;
  background: var(--text-secondary, #616161);
  opacity: 0.2;
  border-radius: 2px;
}

.preview-modern__line.short {
  width: 60%;
}

/* ── Card footer ── */
.template-name {
  padding: 8px 12px 2px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  text-align: center;
}

.template-desc {
  padding: 2px 12px 10px;
  font-size: 11px;
  color: var(--text-secondary, #616161);
  text-align: center;
}
</style>
