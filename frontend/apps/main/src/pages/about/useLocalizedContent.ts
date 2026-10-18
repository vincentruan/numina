import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ContentSection } from './contentTypes'

export function useLocalizedContent(
  zhContent: ContentSection[],
  enContent: ContentSection[],
) {
  const { locale } = useI18n()
  return computed<ContentSection[]>(() =>
    locale.value.startsWith('zh') ? zhContent : enContent,
  )
}
