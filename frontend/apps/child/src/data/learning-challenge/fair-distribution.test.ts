import { describe, it, expect } from 'vitest'
import { getChallengeForTopic } from './fair-distribution'

describe('getChallengeForTopic (U6)', () => {
  it('returns challenge config for known topicKey', () => {
    const challenge = getChallengeForTopic('mt_IHipFGTFEY')
    expect(challenge).not.toBeNull()
    expect(challenge!.id).toBe('fair-distribution-cookies')
    expect(challenge!.type).toBe('distribute')
    expect(challenge!.objects).toHaveLength(8)
    expect(challenge!.zones).toHaveLength(4)
  })

  it('returns null for unknown topicKey', () => {
    const challenge = getChallengeForTopic('nonexistent.topic')
    expect(challenge).toBeNull()
  })

  it('returns null for empty string topicKey', () => {
    const challenge = getChallengeForTopic('')
    expect(challenge).toBeNull()
  })
})
