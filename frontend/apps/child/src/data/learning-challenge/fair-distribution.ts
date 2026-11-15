/**
 * Challenge registry — unified lookup across all challenge types.
 *
 * All challenge configs (distribute, classify, order, balance, pattern,
 * puzzle, estimate, connect, spot-the-mistake, draw-grid) are registered here
 * and looked up by topic_key. The practice flow calls getChallengeForTopic()
 * to determine whether a hands-on challenge exists for the current topic.
 */
import type { ChallengeConfig, DistributeChallenge } from '@/types/learning-challenge'
import { orderFractionsChallenge, orderNumbersChallenge } from './order-challenges'
import { balanceEquationChallenge, balanceWeightsChallenge } from './balance-challenges'
import { classifyLivingChallenge, classifyShapesChallenge } from './classify-challenges'
import { patternFractionNext, patternEmoji } from './pattern-challenges'
import { spotTheMistakeEnglish, spotTheMistakeLearning } from './spot-mistake-challenges'
import { puzzleAreaTiles } from './puzzle-challenges'
import { connectEmotions, connectLifeSkills } from './connect-challenges'
import { estimateJarBeans, estimatePopulation, estimateLifeSkills } from './estimate-challenges'
import { drawGridLetter } from './draw-grid-challenges'
import { orderHistoricalEvents } from './history-order-challenges'

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
export const TOPIC_CHALLENGE_MAP: Record<string, string> = {
  // ── Existing demos (pre-#211) ──
  // Distribute — 理解分数
  mt_IHipFGTFEY: 'fair-distribution-cookies',
  // Order — 比较分数 / 缺失数字问题
  mt_IfEgu0X449: 'order-fractions',
  mt_XuHmIn2xje: 'order-numbers-small',
  // Balance — 寻找加法中的未知数 / 测量质量重量 (R14: remapped from 测量长度)
  mt_ezc2m_0dzN: 'balance-equation-simple',
  mt_zd0YkB3xNj: 'balance-fruit-weights',
  // Classify — 材料分类 / 二维图形
  mt_zHnOGwHIEz: 'classify-living-nonliving',
  mt_vJUa62bxeR: 'classify-shapes-sides',

  // ── mathematics signature (pattern) ──
  'mt_OvyoRo47K-': 'pattern-fraction-next',
  mt_e8CZ7E5qW7: 'pattern-emoji',

  // ── science signature (estimate) ──
  'mt_pwo81ls_J-': 'estimate-jar-beans',
  mt_oLHXfLujmh: 'estimate-population',

  // ── english signature (spot-the-mistake) ──
  mt_scBgiMKhG_: 'mistake-english-grammar',
  mt_GugVunb2lI: 'mistake-english-grammar',

  // ── history signature (order) ──
  mt_IR8kIjZn_V: 'order-historical-events',
  mt_bvxkT1nepy: 'order-historical-events',

  // ── personal_social signature (connect) ──
  mt_kvrvpQris4: 'connect-emotions',
  mt_ggcamLzXAy: 'connect-emotions',

  // ── life_skills signature (estimate) ──
  mt_SbEaQnMQoD: 'estimate-grocery-budget',
  mt_RgQxPddV8v: 'estimate-grocery-budget',

  // ── computing signature (puzzle) ──
  mt_AzTrT5ySCx: 'puzzle-area-tiles',
  mt_XbGfVhfiUz: 'puzzle-area-tiles',

  // ── learning_to_learn signature (spot-the-mistake) ──
  mt_mvXufozy2s: 'mistake-study-habit',
  'mt_8dstvf-KKb': 'mistake-study-habit',

  // ── draw-grid (non-signature, 1 demo) ──
  mt_yJmvUCCym7: 'draw-grid-letter-L',
}

/** All registered challenge configs, keyed by id. */
export const CHALLENGE_CONFIGS: Record<string, ChallengeConfig> = {
  'fair-distribution-cookies': fairDistributionChallenge,
  'order-fractions': orderFractionsChallenge,
  'order-numbers-small': orderNumbersChallenge,
  'balance-equation-simple': balanceEquationChallenge,
  'balance-fruit-weights': balanceWeightsChallenge,
  'classify-living-nonliving': classifyLivingChallenge,
  'classify-shapes-sides': classifyShapesChallenge,
  // New types
  'pattern-fraction-next': patternFractionNext,
  'pattern-emoji': patternEmoji,
  'mistake-english-grammar': spotTheMistakeEnglish,
  'mistake-study-habit': spotTheMistakeLearning,
  'puzzle-area-tiles': puzzleAreaTiles,
  'connect-emotions': connectEmotions,
  'connect-life-skills': connectLifeSkills,
  'estimate-jar-beans': estimateJarBeans,
  'estimate-population': estimatePopulation,
  'estimate-grocery-budget': estimateLifeSkills,
  'draw-grid-letter-L': drawGridLetter,
  'order-historical-events': orderHistoricalEvents,
}

/** Get challenge config for a topic key, or null if none exists. */
export function getChallengeForTopic(topicKey: string): ChallengeConfig | null {
  const configId = TOPIC_CHALLENGE_MAP[topicKey]
  if (!configId) return null
  return CHALLENGE_CONFIGS[configId] ?? null
}
