<script setup lang="ts">
import ContentPage from '@/components/common/ContentPage.vue'
import type { ContentSection } from './contentTypes'

defineProps<{
  title: string
  lastUpdated: string
  content: ContentSection[]
  backTo?: string
}>()
</script>

<template>
  <ContentPage :title="title" :last-updated="lastUpdated" :back-to="backTo">
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
