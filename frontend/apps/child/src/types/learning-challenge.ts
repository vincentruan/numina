/**
 * Challenge configuration types for the ManipulateObserveReflect component (U5).
 *
 * A single reusable "manipulate-observe-reflect" interaction pattern works
 * across subjects by swapping the objects and rules. The interaction supports
 * tap-select and tap-place for accessibility.
 */

/** A single manipulable object the child can place into zones. */
export interface ChallengeObject {
  id: string
  label: string
  labelZh?: string
  /** Optional emoji or icon key for visual representation. */
  icon?: string
}

/** A target zone where objects can be placed. */
export interface ChallengeZone {
  id: string
  label: string
  labelZh?: string
}

/**
 * Discriminated union of challenge types. Each variant defines its objects,
 * zones, and feedback messages. Evaluation dispatches on the `type` tag.
 */
export type ChallengeConfig = DistributeChallenge | ClassifyChallenge

/** Base fields shared by all challenge variants. */
interface ChallengeBase {
  /** Unique identifier for this challenge config. */
  id: string
  /** The topic this challenge belongs to. */
  topicId: string
  /** Curiosity-provoking scenario text (English). */
  scenario: string
  /** Scenario text (Chinese). */
  scenarioZh: string
  /** Message shown when the child succeeds. */
  discoveryMessage: string
  /** Discovery message (Chinese). */
  discoveryMessageZh: string
}

/** Distribute items evenly across targets (e.g., fair sharing). */
export interface DistributeChallenge extends ChallengeBase {
  type: 'distribute'
  objects: ChallengeObject[]
  zones: ChallengeZone[]
}

/** Sort items into categories. */
export interface ClassifyChallenge extends ChallengeBase {
  type: 'classify'
  objects: ChallengeObject[]
  zones: ChallengeZone[]
  /** Maps object id → correct zone id. */
  correctMapping: Record<string, string>
}
