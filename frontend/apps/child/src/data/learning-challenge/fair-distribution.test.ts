import { describe, it, expect } from 'vitest'
import { getChallengeForTopic } from './fair-distribution'

describe('getChallengeForTopic (U6)', () => {
  it('returns challenge config for known topicId', () => {
    const challenge = getChallengeForTopic('math.fractions.understanding')
    expect(challenge).not.toBeNull()
    expect(challenge!.id).toBe('fair-distribution-cookies')
    expect(challenge!.type).toBe('distribute')
    expect(challenge!.objects).toHaveLength(8)
    expect(challenge!.zones).toHaveLength(4)
  })

  it('returns null for unknown topicId', () => {
    const challenge = getChallengeForTopic('nonexistent.topic')
    expect(challenge).toBeNull()
  })

  it('returns null for empty string topicId', () => {
    const challenge = getChallengeForTopic('')
    expect(challenge).toBeNull()
  })
})
