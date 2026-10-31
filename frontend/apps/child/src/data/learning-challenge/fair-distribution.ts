/**
 * Challenge registry — unified lookup across all challenge types.
 *
 * All challenge configs (distribute, classify, order, balance) are registered
 * here and looked up by topic_key. The practice flow calls getChallengeForTopic()
 * to determine whether a hands-on challenge exists for the current topic.
 */
import type { ChallengeConfig, DistributeChallenge } from '@/types/learning-challenge'
import { orderFractionsChallenge, orderNumbersChallenge } from './order-challenges'
import { balanceEquationChallenge, balanceWeightsChallenge } from './balance-challenges'
import { classifyLivingChallenge, classifyShapesChallenge } from './classify-challenges'

// ── Original fair distribution challenge ──

export const fairDistributionChallenge: DistributeChallenge = {
  id: 'fair-distribution-cookies',
  topicId: 'math.fractions.understanding',
  type: 'distribute',
  difficulty: 2,
  ageGroup: 'mid',
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

// ── Registry ──

/**
 * Static lookup: topic_key → challenge config ID.
 *
 * Keyed by `topic_key` (e.g. `mt_IHipFGTFEY`), not a slug — the practice route
 * carries a snowflake topic id, so the caller resolves the key first via
 * `getTopicDetail(topicId)`.
 */
const TOPIC_CHALLENGE_MAP: Record<string, string> = {
  // Distribute — 理解分数
  mt_IHipFGTFEY: 'fair-distribution-cookies',
  // Order — 比较分数 / 缺失数字问题
  mt_IfEgu0X449: 'order-fractions',
  mt_XuHmIn2xje: 'order-numbers-small',
  // Balance — 寻找加法中的未知数 / 测量长度
  mt_ezc2m_0dzN: 'balance-equation-simple',
  mt_skYly2Qm01: 'balance-fruit-weights',
  // Classify — 材料分类 / 二维图形
  mt_zHnOGwHIEz: 'classify-living-nonliving',
  mt_vJUa62bxeR: 'classify-shapes-sides',
}

/** All registered challenge configs, keyed by id. */
const CHALLENGE_CONFIGS: Record<string, ChallengeConfig> = {
  'fair-distribution-cookies': fairDistributionChallenge,
  'order-fractions': orderFractionsChallenge,
  'order-numbers-small': orderNumbersChallenge,
  'balance-equation-simple': balanceEquationChallenge,
  'balance-fruit-weights': balanceWeightsChallenge,
  'classify-living-nonliving': classifyLivingChallenge,
  'classify-shapes-sides': classifyShapesChallenge,
}

/** Get challenge config for a topic key, or null if none exists. */
export function getChallengeForTopic(topicKey: string): ChallengeConfig | null {
  const configId = TOPIC_CHALLENGE_MAP[topicKey]
  if (!configId) return null
  return CHALLENGE_CONFIGS[configId] ?? null
}
