/**
 * WelcomePage suggestion pool
 *
 * Pre-generated 30 questions per agent. Each question has:
 * - title:    short label used internally / for accessibility (≤6 chars)
 * - summary:  1-2 sentence preview shown on the card (the user-facing text)
 * - prompt:   full text sent to the agent when the user taps the card
 *
 * i18n keys live under `aiChat.welcomeQ.*` (zh-CN / en-US).
 */
import { useI18n } from 'vue-i18n'

export interface WelcomeQuestion {
  /** i18n key suffix under aiChat.welcomeQ.<key>.{title,summary,prompt} */
  key: string
}

/** Resolved question with localized text fields */
export interface ResolvedWelcomeQuestion {
  key: string
  title: string
  summary: string
  prompt: string
}

/** numina (家庭资产管理助手) — 30 questions */
const NUMINA_KEYS: WelcomeQuestion[] = [
  { key: 'n01' }, { key: 'n02' }, { key: 'n03' }, { key: 'n04' }, { key: 'n05' },
  { key: 'n06' }, { key: 'n07' }, { key: 'n08' }, { key: 'n09' }, { key: 'n10' },
  { key: 'n11' }, { key: 'n12' }, { key: 'n13' }, { key: 'n14' }, { key: 'n15' },
  { key: 'n16' }, { key: 'n17' }, { key: 'n18' }, { key: 'n19' }, { key: 'n20' },
  { key: 'n21' }, { key: 'n22' }, { key: 'n23' }, { key: 'n24' }, { key: 'n25' },
  { key: 'n26' }, { key: 'n27' }, { key: 'n28' }, { key: 'n29' }, { key: 'n30' },
]

/** chat (通用智能体) — 30 questions */
const CHAT_KEYS: WelcomeQuestion[] = [
  { key: 'c01' }, { key: 'c02' }, { key: 'c03' }, { key: 'c04' }, { key: 'c05' },
  { key: 'c06' }, { key: 'c07' }, { key: 'c08' }, { key: 'c09' }, { key: 'c10' },
  { key: 'c11' }, { key: 'c12' }, { key: 'c13' }, { key: 'c14' }, { key: 'c15' },
  { key: 'c16' }, { key: 'c17' }, { key: 'c18' }, { key: 'c19' }, { key: 'c20' },
  { key: 'c21' }, { key: 'c22' }, { key: 'c23' }, { key: 'c24' }, { key: 'c25' },
  { key: 'c26' }, { key: 'c27' }, { key: 'c28' }, { key: 'c29' }, { key: 'c30' },
]

/**
 * Resolve the pool for the active agent. numina → finance pool, everything
 * else → chat pool. Returns exactly 30 entries for random-pick.
 */
export function useWelcomeQuestions(agentName?: string) {
  const { t } = useI18n()
  const pool = agentName === 'chat' ? CHAT_KEYS : NUMINA_KEYS

  /** Resolve title + summary + prompt for a question entry (live i18n lookup) */
  function resolve(q: WelcomeQuestion): ResolvedWelcomeQuestion {
    return {
      key: q.key,
      title: t(`aiChat.welcomeQ.${q.key}.title`),
      summary: t(`aiChat.welcomeQ.${q.key}.summary`),
      prompt: t(`aiChat.welcomeQ.${q.key}.prompt`),
    }
  }

  /** Pick N random questions from the pool without replacement */
  function pickRandom(n = 3): ResolvedWelcomeQuestion[] {
    const copy = [...pool]
    const out: ResolvedWelcomeQuestion[] = []
    for (let i = 0; i < n && copy.length > 0; i++) {
      const idx = Math.floor(Math.random() * copy.length)
      const [q] = copy.splice(idx, 1)
      out.push(resolve(q))
    }
    return out
  }

  return { pool, resolve, pickRandom }
}
