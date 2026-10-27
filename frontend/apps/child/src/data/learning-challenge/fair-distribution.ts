/**
 * Fair distribution challenge — fractions P1 sample (U6).
 *
 * A concrete DistributeChallenge config for the "fair sharing" math topic.
 * The child distributes cookies equally among friends to explore fractions.
 */
import type { DistributeChallenge } from '@/types/learning-challenge'

export const fairDistributionChallenge: DistributeChallenge = {
  id: 'fair-distribution-cookies',
  topicId: 'math.fractions.understanding',
  type: 'distribute',
  scenario:
    'At a picnic, 4 friends want to share 8 cookies fairly. How can you divide them so everyone gets the same amount?',
  scenarioZh: '野餐时，4个朋友想公平分享8块饼干。怎样分才能让每个人得到相同的一份？',
  discoveryMessage:
    'You made sure everyone got the same amount! That\'s what fair sharing means — 8 ÷ 4 = 2 each.',
  discoveryMessageZh:
    '你让每个人都分到了相同数量的饼干！这就是公平分配——每人得到 8÷4=2 块。',
  objects: [
    { id: 'cookie-1', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
    { id: 'cookie-2', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
    { id: 'cookie-3', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
    { id: 'cookie-4', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
    { id: 'cookie-5', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
    { id: 'cookie-6', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
    { id: 'cookie-7', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
    { id: 'cookie-8', label: 'Cookie', labelZh: '饼干', icon: '🍪' },
  ],
  zones: [
    { id: 'friend-a', label: 'Friend A', labelZh: '小明' },
    { id: 'friend-b', label: 'Friend B', labelZh: '小红' },
    { id: 'friend-c', label: 'Friend C', labelZh: '小华' },
    { id: 'friend-d', label: 'Friend D', labelZh: '小丽' },
  ],
}

/** Static lookup: topic_key → challenge config ID. P1 has one challenge.
 *
 * Keyed by `topic_key` (e.g. `mt_IHipFGTFEY`), not a slug — the practice route
 * carries a snowflake topic id, so the caller resolves the key first via
 * `getTopicDetail(topicId)`.
 */
const TOPIC_CHALLENGE_MAP: Record<string, string> = {
  mt_IHipFGTFEY: 'fair-distribution-cookies',
}

/** All registered challenge configs. */
const CHALLENGE_CONFIGS: Record<string, DistributeChallenge> = {
  'fair-distribution-cookies': fairDistributionChallenge,
}

/** Get challenge config for a topic key, or null if none exists. */
export function getChallengeForTopic(topicKey: string): DistributeChallenge | null {
  const configId = TOPIC_CHALLENGE_MAP[topicKey]
  if (!configId) return null
  return CHALLENGE_CONFIGS[configId] ?? null
}
