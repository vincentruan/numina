<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import LegalDocumentPage from './LegalDocumentPage.vue'
import { termsContent as termsZh } from './data/terms-zh'
import { termsContent as termsEn } from './data/terms-en'
import { useLocalizedContent } from './useLocalizedContent'

const { t } = useI18n()
const content = useLocalizedContent(termsZh, termsEn)
</script>

<template>
  <LegalDocumentPage
    :title="t('settings.termsOfService')"
    last-updated="2026-10-18"
    :content="content"
    back-to="/settings/about"
  />
</template>
