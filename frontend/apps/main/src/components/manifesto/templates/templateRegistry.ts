import type { TemplateDefinition } from '@/types/manifesto'
import ClassicTemplate from './ClassicTemplate.vue'
import ModernTemplate from './ModernTemplate.vue'

export const TEMPLATES: TemplateDefinition[] = [
  { id: 'classic-zh', nameKey: 'manifesto.template.classic', lang: 'zh', type: 'classic', component: ClassicTemplate },
  { id: 'classic-en', nameKey: 'manifesto.template.classic', lang: 'en', type: 'classic', component: ClassicTemplate },
  { id: 'modern-zh', nameKey: 'manifesto.template.modern', lang: 'zh', type: 'modern', component: ModernTemplate },
  { id: 'modern-en', nameKey: 'manifesto.template.modern', lang: 'en', type: 'modern', component: ModernTemplate },
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

/** Resolve a member role to its i18n label. Shared by all templates. */
export function getRoleLabel(role: string, t: (key: string) => string): string {
  if (role === 'owner') return t('manifesto.ownerRole')
  if (role === 'member') return t('manifesto.memberRole')
  return t('manifesto.childRole')
}
