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
        :class="{ selected: state.selectedTemplateId === tmpl.id }"
        @click="selectTemplate(tmpl.id)"
      >
        <div class="template-preview" :class="tmpl.lang === 'zh' ? 'preview-zh' : 'preview-en'">
          <div class="preview-title">{{ t(tmpl.nameKey) }}</div>
          <div class="preview-line" />
          <div class="preview-line short" />
        </div>
        <div class="template-name">{{ t(tmpl.nameKey) }}</div>
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

const sortedTemplates = computed(() => getTemplatesSorted(ownerLang.value))

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
  gap: 12px;
  padding: 16px;
}

.template-card {
  border: 2px solid var(--color-border, #dcdfe6);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  background: var(--card-bg, #fff);
  transition: border-color 0.2s;
}

.template-card.selected {
  border-color: var(--van-primary-color, #1989fa);
}

.template-preview {
  height: 120px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-zh {
  background: linear-gradient(135deg, rgba(255, 215, 0, 0.12), rgba(255, 165, 0, 0.08));
}

.preview-en {
  background: linear-gradient(135deg, rgba(100, 149, 237, 0.12), rgba(70, 130, 180, 0.08));
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  text-align: center;
}

.preview-line {
  height: 4px;
  background: var(--text-secondary, #616161);
  opacity: 0.3;
  border-radius: 2px;
}

.preview-line.short {
  width: 60%;
  align-self: center;
}

.template-name {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary, #0a0a0a);
  text-align: center;
  border-top: 1px solid var(--color-border, #dcdfe6);
}
</style>
