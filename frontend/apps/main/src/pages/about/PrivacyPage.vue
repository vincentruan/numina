<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { privacyContent as privacyZh } from './data/privacy-zh'
import { privacyContent as privacyEn } from './data/privacy-en'
import type { ContentSection } from './contentTypes'

const { t, locale } = useI18n()

const content = computed<ContentSection[]>(() =>
  locale.value.startsWith('zh') ? privacyZh : privacyEn,
)
</script>

<template>
  <ContentPage :title="t('settings.privacyPolicy')" last-updated="2026-10-18">
    <section v-for="section in content" :key="section.heading">
      <h2>{{ section.heading }}</h2>
      <template v-for="(block, idx) in section.blocks" :key="idx">
        <p v-if="block.type === 'paragraph'">{{ block.text }}</p>
        <ul v-else-if="block.type === 'list'">
          <li v-for="(item, iidx) in block.items" :key="iidx">{{ item }}</li>
        </ul>
      </template>
    </section>
  </ContentPage>
</template>
