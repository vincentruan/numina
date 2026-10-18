<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import LegalDocumentPage from './LegalDocumentPage.vue'
import { privacyContent as privacyZh } from './data/privacy-zh'
import { privacyContent as privacyEn } from './data/privacy-en'

const { t, locale } = useI18n()

const content = computed(() =>
  locale.value.startsWith('zh') ? privacyZh : privacyEn,
)
</script>

<template>
  <LegalDocumentPage
    :title="t('settings.privacyPolicy')"
    last-updated="2026-10-18"
    :content="content"
    back-to="/settings/about"
  />
</template>
