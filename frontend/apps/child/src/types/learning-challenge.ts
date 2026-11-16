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
export type ChallengeConfig =
  | DistributeChallenge
  | ClassifyChallenge
  | OrderChallenge
  | BalanceChallenge
  | PatternChallenge
  | PuzzleChallenge
  | EstimateChallenge
  | ConnectChallenge
  | SpotTheMistakeChallenge
  | DrawGridChallenge

/** Every registered challenge type discriminator. */
export type ChallengeType = ChallengeConfig['type']

/**
 * Three-state verdict shared by every challenge type.
 * `close` is visually distinct from `wrong` so a nearly-correct attempt reads
 * as encouragement rather than failure.
 */
export type ChallengeVerdict = 'correct' | 'close' | 'wrong'

/** Result of evaluating a child's attempt at any challenge type. */
export interface ChallengeJudgement {
  verdict: ChallengeVerdict
  hint: string
}

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
  /**
   * The concept name revealed after the discovery moment (English).
   * E.g., "fractions", "symmetry", "equality"
   * Shown as: "What you just did is called 'fractions'!"
   */
  conceptName?: string
  /** Concept name (Chinese). */
  conceptNameZh?: string
  /** Difficulty level 1-5. Maps to backend adaptive difficulty ranges. */
  difficulty: number
  /** Target age group: early (6-8), mid (8-10), late (10-12). */
  ageGroup: 'early' | 'mid' | 'late'
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

/** Arrange items in the correct sequential order (seriation / ordinal reasoning). */
export interface OrderChallenge extends ChallengeBase {
  type: 'order'
  objects: ChallengeObject[]
  /** Object IDs in correct sequential order (index 0 = first/leftmost). */
  correctOrder: string[]
}

/** Balance a scale by matching the total value on both sides (algebraic thinking). */
export interface BalanceChallenge extends ChallengeBase {
  type: 'balance'
  /** Fixed items on the left side (cannot be moved). */
  leftFixed: ChallengeObject[]
  /** Number of empty slots on the right side where child places objects. */
  rightSlots: number
  /** Available objects to place on the right side. */
  objects: ChallengeObject[]
  /** Numeric value of each object (for weight calculation). Keyed by object id. */
  objectValues: Record<string, number>
}

/** Pick the next item in a sequence (pattern recognition). */
export interface PatternChallenge extends ChallengeBase {
  type: 'pattern'
  /** The visible prefix of the sequence, in order. */
  sequence: ChallengeObject[]
  /** Candidate answers the child taps to choose the next item. */
  options: ChallengeObject[]
  /** Id of the option that correctly continues the sequence. */
  correctAnswer: string
}

/** Place puzzle pieces into their correct slots (spatial/area reasoning). */
export interface PuzzleChallenge extends ChallengeBase {
  type: 'puzzle'
  /** Slots the child fills, in display order. */
  slots: ChallengeObject[]
  /** Pieces available to place (may outnumber slots). */
  objects: ChallengeObject[]
  /** Maps slot id → the object id that belongs there. */
  correctPlacement: Record<string, string>
}

/** Estimate a quantity using tap-step input (number sense, magnitude). */
export interface EstimateChallenge extends ChallengeBase {
  type: 'estimate'
  /** Starting value shown before any step is taken. */
  startValue: number
  /** Increment per tap of +/-. Must reach `targetValue` in whole steps. */
  step: number
  /** The quantity being estimated. */
  targetValue: number
  /** Absolute error at or below this is `correct`. */
  narrowTolerance: number
  /** Absolute error at or below this (but above narrow) is `close`. */
  wideTolerance: number
  /** Unit label for the displayed value, e.g. "beans". */
  unitLabel: string
  unitLabelZh?: string
}

/** Pair related items across two columns (relationships, equivalence). */
export interface ConnectChallenge extends ChallengeBase {
  type: 'connect'
  /** Left column items. */
  leftItems: ChallengeObject[]
  /** Right column items. */
  rightItems: ChallengeObject[]
  /** Maps left item id → the right item id it pairs with. */
  correctPairs: Record<string, string>
}

/** Identify which line of a worked example is wrong (error analysis). */
export interface SpotTheMistakeChallenge extends ChallengeBase {
  type: 'spot-the-mistake'
  /** The worked example, split into numbered lines. */
  lines: string[]
  /** Chinese rendering of the same lines, index-aligned with `lines`. */
  linesZh?: string[]
  /** Index into `lines` of the incorrect step. */
  mistakeLineIndex: number
}

/** Fill a grid to match a stated target (area, shape composition). */
export interface DrawGridChallenge extends ChallengeBase {
  type: 'draw-grid'
  /** Number of rows in the grid. */
  gridRows: number
  /** Number of columns in the grid. */
  gridCols: number
  /**
   * Target layout as row-major filled-cell keys, e.g. `['0-0', '0-1']` for
   * the first two cells of row 0. The scenario text must state this layout
   * explicitly so the child can aim at it.
   */
  targetCells: string[]
}
