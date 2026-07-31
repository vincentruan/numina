import type { TemplateDefinition } from '@/types/manifesto'
import ClassicTemplate from './ClassicTemplate.vue'
import ModernTemplate from './ModernTemplate.vue'

export const TEMPLATES: TemplateDefinition[] = [
  { id: 'classic-zh', nameKey: 'manifesto.template.classic', lang: 'zh', component: ClassicTemplate },
  { id: 'classic-en', nameKey: 'manifesto.template.classic', lang: 'en', component: ClassicTemplate },
  { id: 'modern-zh', nameKey: 'manifesto.template.modern', lang: 'zh', component: ModernTemplate },
  { id: 'modern-en', nameKey: 'manifesto.template.modern', lang: 'en', component: ModernTemplate },
]

export function getTemplate(id: string): TemplateDefinition | undefined {
  return TEMPLATES.find(t => t.id === id)
}

export function getTemplatesSorted(ownerLang: string): TemplateDefinition[] {
  return [...TEMPLATES].sort((a, b) => {
    if (a.lang === ownerLang && b.lang !== ownerLang) return -1
    if (a.lang !== ownerLang && b.lang === ownerLang) return 1
    return 0
  })
}
