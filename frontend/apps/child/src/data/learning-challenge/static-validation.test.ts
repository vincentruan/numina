/**
 * Static consistency checks for the challenge configuration.
 *
 * These catch configuration drift that no component test would notice: a
 * topic key that no longer exists in the taxonomy, a duplicated config id, a
 * signature pointing at an unregistered type, or an estimate whose target the
 * stepper can never reach.
 */
import { describe, it, expect } from 'vitest'
import { CHALLENGE_CONFIGS, TOPIC_CHALLENGE_MAP } from './fair-distribution'
import { SUBJECT_SIGNATURE, SUBJECT_SLUGS } from './subject-signature'
import { resolveChallengeComponent } from '@/components/learning/challenges'
import type { EstimateChallenge } from '@/types/learning-challenge'
import taxonomy from './__fixtures__/taxonomy-snapshot.json'

interface TaxonomySnapshot {
  topics: Array<{ id: string; subject: string; name: string }>
}

const snapshot = taxonomy as TaxonomySnapshot

const taxonomyIds = new Set(snapshot.topics.map((t) => t.id))

/** Every discriminator the dispatcher can actually resolve. */
function registeredDiscriminators(): Set<string> {
  // Probe the dispatcher rather than reaching into its private registry
  const candidates = [
    'distribute',
    'classify',
    'order',
    'balance',
    'pattern',
    'puzzle',
    'estimate',
    'connect',
    'spot-the-mistake',
    'draw-grid',
  ]
  return new Set(candidates.filter((t) => resolveChallengeComponent(t) !== null))
}

describe('challenge configuration consistency', () => {
  it('every mapped topic key resolves in the taxonomy', () => {
    const unresolved = Object.keys(TOPIC_CHALLENGE_MAP).filter((k) => !taxonomyIds.has(k))
    expect(unresolved).toEqual([])
  })

  it('every mapped config id exists in the config registry', () => {
    const missing = Object.entries(TOPIC_CHALLENGE_MAP)
      .filter(([, configId]) => !(configId in CHALLENGE_CONFIGS))
      .map(([topicKey, configId]) => `${topicKey} → ${configId}`)
    expect(missing).toEqual([])
  })

  it('each config id is unique across the registry', () => {
    const ids = Object.values(CHALLENGE_CONFIGS).map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('each config id equals its registry key', () => {
    const mismatched = Object.entries(CHALLENGE_CONFIGS)
      .filter(([key, config]) => key !== config.id)
      .map(([key, config]) => `${key} vs ${config.id}`)
    expect(mismatched).toEqual([])
  })

  it('every signature points at a registered discriminator', () => {
    const registered = registeredDiscriminators()
    const unregistered = Object.entries(SUBJECT_SIGNATURE)
      .filter(([, type]) => !registered.has(type))
      .map(([subject, type]) => `${subject} → ${type}`)
    expect(unregistered).toEqual([])
  })

  it('every signature key is a valid subject slug', () => {
    const invalid = Object.keys(SUBJECT_SIGNATURE).filter((s) => !SUBJECT_SLUGS.includes(s))
    expect(invalid).toEqual([])
  })

  it('all eight subjects have a signature', () => {
    expect(Object.keys(SUBJECT_SIGNATURE).sort()).toEqual([...SUBJECT_SLUGS].sort())
  })

  it('every estimate target is reachable from its start value in whole steps', () => {
    const unreachable = Object.values(CHALLENGE_CONFIGS)
      .filter((c): c is EstimateChallenge => c.type === 'estimate')
      .filter((c) => {
        const steps = (c.targetValue - c.startValue) / c.step
        return !Number.isInteger(steps)
      })
      .map((c) => c.id)
    expect(unreachable).toEqual([])
  })

  it('every estimate keeps narrow tolerance at or below wide', () => {
    const bad = Object.values(CHALLENGE_CONFIGS)
      .filter((c): c is EstimateChallenge => c.type === 'estimate')
      .filter((c) => c.narrowTolerance > c.wideTolerance)
      .map((c) => c.id)
    expect(bad).toEqual([])
  })
})
