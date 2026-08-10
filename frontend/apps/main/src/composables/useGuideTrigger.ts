import type { UserConfigValues } from '@/api/config'
import { updateUserConfig } from '@/api/config'

const COMPLETION_RATE_THRESHOLD = 20
const MIN_ATTEMPTS_FOR_RATE_CHECK = 3
const MIN_INTERVAL_MS = 24 * 60 * 60 * 1000
const LAST_SHOWN_KEY = 'guide_last_shown_ts'

export interface GuideTriggerResult {
  shouldShow: boolean
  reason: string
}

export function shouldShowGuide(
  config: Pick<UserConfigValues, 'onboarding_guide_version' | 'onboarding_attempts' | 'onboarding_completions'>,
  currentVersion: number,
): GuideTriggerResult {
  const { onboarding_guide_version: version, onboarding_attempts: attempts, onboarding_completions: completions } = config

  if (version >= currentVersion) return { shouldShow: false, reason: 'already_done' }

  if (attempts >= MIN_ATTEMPTS_FOR_RATE_CHECK) {
    const rate = Math.round((completions / attempts) * 100)
    if (rate < COMPLETION_RATE_THRESHOLD) return { shouldShow: false, reason: 'low_completion_rate' }
  }

  const lastShown = Number(localStorage.getItem(LAST_SHOWN_KEY) ?? 0)
  if (lastShown > 0 && Date.now() - lastShown < MIN_INTERVAL_MS) return { shouldShow: false, reason: 'recently_shown' }

  const reason = attempts === 0 ? 'first_visit' : 'version_bump'
  return { shouldShow: true, reason }
}

export function recordGuideShown(): void {
  localStorage.setItem(LAST_SHOWN_KEY, String(Date.now()))
}

export async function recordGuideAttempt(config: UserConfigValues): Promise<void> {
  await updateUserConfig({ onboarding_attempts: config.onboarding_attempts + 1 })
}

export async function recordGuideCompletion(config: UserConfigValues, version: number): Promise<void> {
  await updateUserConfig({
    onboarding_guide_version: version,
    onboarding_completions: config.onboarding_completions + 1,
  })
}

export async function resetGuideState(): Promise<void> {
  // Clear all guide-related localStorage keys (includes step-guide completion
  // markers like 'guide_main-onboarding-v2' that useStepGuide.start() checks).
  Object.keys(localStorage)
    .filter(k => k.startsWith('guide_'))
    .forEach(k => localStorage.removeItem(k))
  await updateUserConfig({
    onboarding_guide_version: 0,
    onboarding_attempts: 0,
    onboarding_completions: 0,
  })
}
