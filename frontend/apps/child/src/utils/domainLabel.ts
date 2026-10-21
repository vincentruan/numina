import type { ComposerTranslation } from 'vue-i18n'

/**
 * Translate a taxonomy domain name, falling back to the raw string when the
 * locale has no entry for it.
 *
 * `__other__` is the synthetic bucket for topics whose domain has no cluster;
 * its raw id must never reach the UI.
 */
export function domainLabel(t: ComposerTranslation, domain: string): string {
  if (domain === '__other__') return t('learning.cluster.otherDomain')
  const key = `learning.domains.${domain}`
  const translated = t(key)
  return translated === key ? domain : translated
}
