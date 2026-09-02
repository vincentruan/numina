/**
 * Shared report utilities.
 *
 * Extracted to avoid duplicating indicator-label resolution across
 * AIHubPage and AIReportPage.
 */

import type { Composer } from 'vue-i18n'

/**
 * Resolve an indicator's display label from i18n.
 * Falls back to the raw key when no translation exists (e.g. a new
 * indicator key that hasn't been added to the locale file yet).
 */
export function getIndicatorLabel(key: string, t: Composer['t']): string {
  const i18nKey = `aiReport.indicatorLabel_${key}`
  const translated = t(i18nKey)
  return translated !== i18nKey ? translated : key
}
