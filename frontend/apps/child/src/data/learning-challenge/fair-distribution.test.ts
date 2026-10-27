import { describe, it, expect } from 'vitest'
import { getChallengeForTopic } from './fair-distribution'
import type { DistributeChallenge } from '@/types/learning-challenge'

describe('getChallengeForTopic (U6)', () => {
  it('returns challenge config for known topicKey', () => {
    const challenge = getChallengeForTopic('mt_IHipFGTFEY')
    expect(challenge).not.toBeNull()
    expect(challenge!.id).toBe('fair-distribution-cookies')
    expect(challenge!.type).toBe('distribute')
    // Narrow to DistributeChallenge since type === 'distribute'
    const dist = challenge as DistributeChallenge
    expect(dist.objects).toHaveLength(8)
    expect(dist.zones).toHaveLength(4)
  })

  it('returns null for unknown topicKey', () => {
    const challenge = getChallengeForTopic('nonexistent.topic')
    expect(challenge).toBeNull()
  })

  it('returns null for empty string topicKey', () => {
    const challenge = getChallengeForTopic('')
    expect(challenge).toBeNull()
  })

  it('returns order challenge for ordering topic', () => {
    const challenge = getChallengeForTopic('mt_IfEgu0X449')
    expect(challenge).not.toBeNull()
    expect(challenge!.type).toBe('order')
    expect(challenge!.difficulty).toBe(2)
    expect(challenge!.ageGroup).toBe('mid')
  })

  it('returns balance challenge for equation topic', () => {
    const challenge = getChallengeForTopic('mt_ezc2m_0dzN')
    expect(challenge).not.toBeNull()
    expect(challenge!.type).toBe('balance')
    expect(challenge!.difficulty).toBe(2)
  })

  it('returns classify challenge for science topic', () => {
    const challenge = getChallengeForTopic('mt_zHnOGwHIEz')
    expect(challenge).not.toBeNull()
    expect(challenge!.type).toBe('classify')
    expect(challenge!.difficulty).toBe(1)
    expect(challenge!.ageGroup).toBe('early')
  })

  it('all registered challenges have required base fields', () => {
    const knownKeys = [
      'mt_IHipFGTFEY',
      'mt_IfEgu0X449',
      'mt_XuHmIn2xje',
      'mt_ezc2m_0dzN',
      'mt_skYly2Qm01',
      'mt_zHnOGwHIEz',
      'mt_vJUa62bxeR',
    ]
    for (const key of knownKeys) {
      const c = getChallengeForTopic(key)
      expect(c, `missing challenge for ${key}`).not.toBeNull()
      expect(c!.id, `${key}: missing id`).toBeTruthy()
      expect(c!.scenario, `${key}: missing scenario`).toBeTruthy()
      expect(c!.scenarioZh, `${key}: missing scenarioZh`).toBeTruthy()
      expect(c!.discoveryMessage, `${key}: missing discoveryMessage`).toBeTruthy()
      expect(c!.discoveryMessageZh, `${key}: missing discoveryMessageZh`).toBeTruthy()
      expect(c!.difficulty, `${key}: missing difficulty`).toBeGreaterThanOrEqual(1)
      expect(c!.difficulty, `${key}: difficulty out of range`).toBeLessThanOrEqual(5)
      expect(['early', 'mid', 'late'], `${key}: invalid ageGroup`).toContain(c!.ageGroup)
    }
  })
})
