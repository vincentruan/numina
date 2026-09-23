import { useI18n } from 'vue-i18n'

interface LocalizedTopic {
  name: string | null
  name_zh: string | null
  description: string
  description_zh: string | null
  topic_key?: string
}

/**
 * Resolve topic display name/description based on current locale.
 */
export function useLocalizedTopic() {
  const { locale } = useI18n()

  function topicDisplayName(topic: LocalizedTopic): string {
    if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
    return topic.name || topic.topic_key || ''
  }

  function topicDescription(topic: LocalizedTopic): string {
    if (locale.value.startsWith('zh') && topic.description_zh) return topic.description_zh
    return topic.description
  }

  return { topicDisplayName, topicDescription }
}
