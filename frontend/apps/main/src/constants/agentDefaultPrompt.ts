/** Returns the i18n-translated default prompt for the Numina agent. */
export function getXiaomingDefaultPrompt(t: (key: string) => string): string {
  return t('aiChat.xiaomingDefaultPrompt')
}

export const SYSTEM_DEFAULT_SESSION_MAX_AGE_HOURS = 6
