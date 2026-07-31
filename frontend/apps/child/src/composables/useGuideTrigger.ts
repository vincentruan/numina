import http from '@/api/index'

const COMPLETION_RATE_THRESHOLD = 20
const MIN_ATTEMPTS_FOR_RATE_CHECK = 3
const MIN_INTERVAL_MS = 24 * 60 * 60 * 1000
const LAST_SHOWN_KEY = 'guide_last_shown_ts'

interface OnboardingConfig {
  onboarding_guide_version: number
  onboarding_attempts: number
  onboarding_completions: number
}

export async function shouldShowChildGuide(currentVersion: number): Promise<{
  shouldShow: boolean
  reason: string
  config: OnboardingConfig
}> {
  let config: OnboardingConfig
  try {
    const res = await http.get<OnboardingConfig>('/user/config')
    config = res.data
  } catch {
    return { shouldShow: false, reason: 'api_error', config: { onboarding_guide_version: 0, onboarding_attempts: 0, onboarding_completions: 0 } }
  }

  if (config.onboarding_guide_version >= currentVersion) return { shouldShow: false, reason: 'already_done', config }

  if (config.onboarding_attempts >= MIN_ATTEMPTS_FOR_RATE_CHECK) {
    const rate = config.onboarding_attempts > 0 ? Math.round((config.onboarding_completions / config.onboarding_attempts) * 100) : 0
    if (rate < COMPLETION_RATE_THRESHOLD) return { shouldShow: false, reason: 'low_completion_rate', config }
  }

  const lastShown = Number(localStorage.getItem(LAST_SHOWN_KEY) ?? 0)
  if (lastShown > 0 && Date.now() - lastShown < MIN_INTERVAL_MS) return { shouldShow: false, reason: 'recently_shown', config }

  const reason = config.onboarding_attempts === 0 ? 'first_visit' : 'version_bump'
  return { shouldShow: true, reason, config }
}

export function recordChildGuideShown(): void {
  localStorage.setItem(LAST_SHOWN_KEY, String(Date.now()))
}

export async function recordChildGuideAttempt(config: OnboardingConfig): Promise<void> {
  await http.patch('/user/config', { settings: { onboarding_attempts: config.onboarding_attempts + 1 } })
}

export async function recordChildGuideCompletion(config: OnboardingConfig, version: number): Promise<void> {
  await http.patch('/user/config', { settings: { onboarding_guide_version: version, onboarding_completions: config.onboarding_completions + 1 } })
}
