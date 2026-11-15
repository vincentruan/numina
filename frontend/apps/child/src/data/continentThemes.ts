/**
 * Continent themes — visual identity for each subject area.
 *
 * Each subject is rendered as an "island" on the knowledge ocean map with its own
 * terrain type, color palette, and marker icon. These themes drive the
 * KnowledgeOcean view and the continent-canvas styling.
 */

export type Terrain = 'math' | 'science' | 'language' | 'social' | 'arts' | 'default'

export interface ContinentTheme {
  /** Subject key (matches LearningTopic.subject) */
  subject: string
  /** Terrain class for CSS hooks (e.g. 'territory--math') */
  terrain: Terrain
  /** Emoji marker for the continent */
  icon: string
  /** Primary color (CSS custom property or hex) */
  color: string
  /** Secondary/accent color */
  accent: string
  /** Display name key for i18n */
  nameKey: string
}

/**
 * Subject → continent theme metadata.
 *
 * Single source of truth for continent visual identity. Used by:
 * - KnowledgeOcean.vue (subject islands on the ocean map)
 * - ClusterTerritory.vue (territory theming)
 * - ClusterMap.vue (continent-canvas background)
 */
export const CONTINENT_THEMES: Record<string, ContinentTheme> = {
  mathematics: {
    subject: 'mathematics',
    terrain: 'math',
    icon: '📐',
    color: 'var(--color-brand-ochre)',
    accent: 'var(--color-brand-ochre-light, #fef3d9)',
    nameKey: 'learning.subject.mathematics',
  },
  science: {
    subject: 'science',
    terrain: 'science',
    icon: '🔬',
    color: 'var(--color-brand-teal)',
    accent: 'var(--color-brand-teal-light, #e6f7f5)',
    nameKey: 'learning.subject.science',
  },
  chinese: {
    subject: 'chinese',
    terrain: 'language',
    icon: '📖',
    color: 'var(--color-brand-coral)',
    accent: 'var(--color-brand-coral-light, #fde8e4)',
    nameKey: 'learning.subject.chinese',
  },
  english: {
    subject: 'english',
    terrain: 'language',
    icon: '🔤',
    color: 'var(--color-brand-lavender)',
    accent: 'var(--color-brand-lavender-light, #f0e6ff)',
    nameKey: 'learning.subject.english',
  },
  physics: {
    subject: 'physics',
    terrain: 'science',
    icon: '⚡',
    color: 'var(--color-brand-teal)',
    accent: 'var(--color-brand-teal-light, #e6f7f5)',
    nameKey: 'learning.subject.physics',
  },
  chemistry: {
    subject: 'chemistry',
    terrain: 'science',
    icon: '🧪',
    color: 'var(--color-brand-sage)',
    accent: 'var(--color-brand-sage-light, #e8f5e9)',
    nameKey: 'learning.subject.chemistry',
  },
  biology: {
    subject: 'biology',
    terrain: 'science',
    icon: '🌿',
    color: 'var(--color-brand-sage)',
    accent: 'var(--color-brand-sage-light, #e8f5e9)',
    nameKey: 'learning.subject.biology',
  },
  history: {
    subject: 'history',
    terrain: 'social',
    icon: '📜',
    color: 'var(--color-brand-ochre)',
    accent: 'var(--color-brand-ochre-light, #fef3d9)',
    nameKey: 'learning.subject.history',
  },
  geography: {
    subject: 'geography',
    terrain: 'social',
    icon: '🌍',
    color: 'var(--color-brand-sage)',
    accent: 'var(--color-brand-sage-light, #e8f5e9)',
    nameKey: 'learning.subject.geography',
  },
  politics: {
    subject: 'politics',
    terrain: 'social',
    icon: '🏛',
    color: 'var(--color-brand-lavender)',
    accent: 'var(--color-brand-lavender-light, #f0e6ff)',
    nameKey: 'learning.subject.politics',
  },
  art: {
    subject: 'art',
    terrain: 'arts',
    icon: '🎨',
    color: 'var(--color-brand-coral)',
    accent: 'var(--color-brand-coral-light, #fde8e4)',
    nameKey: 'learning.subject.art',
  },
  music: {
    subject: 'music',
    terrain: 'arts',
    icon: '🎵',
    color: 'var(--color-brand-lavender)',
    accent: 'var(--color-brand-lavender-light, #f0e6ff)',
    nameKey: 'learning.subject.music',
  },
  physical_education: {
    subject: 'physical_education',
    terrain: 'arts',
    icon: '🏃',
    color: 'var(--color-brand-teal)',
    accent: 'var(--color-brand-teal-light, #e6f7f5)',
    nameKey: 'learning.subject.physical_education',
  },
  information_technology: {
    subject: 'information_technology',
    terrain: 'science',
    icon: '💻',
    color: 'var(--color-brand-teal)',
    accent: 'var(--color-brand-teal-light, #e6f7f5)',
    nameKey: 'learning.subject.information_technology',
  },
  // --- os-taxonomy subjects missing before the castle slice (U3) ---
  computing: {
    subject: 'computing',
    terrain: 'science',
    icon: '🖥',
    color: 'var(--color-brand-teal)',
    accent: 'var(--color-brand-mint, #a4d4c5)',
    nameKey: 'learning.subject.computing',
  },
  learning_to_learn: {
    subject: 'learning_to_learn',
    terrain: 'social',
    icon: '🧠',
    color: 'var(--color-brand-lavender)',
    accent: 'var(--color-brand-lavender, #b8a4ed)',
    nameKey: 'learning.subject.learning_to_learn',
  },
  life_skills: {
    subject: 'life_skills',
    terrain: 'arts',
    icon: '🧺',
    color: 'var(--color-brand-mint)',
    accent: 'var(--color-brand-mint, #a4d4c5)',
    nameKey: 'learning.subject.life_skills',
  },
  personal_social: {
    subject: 'personal_social',
    terrain: 'social',
    icon: '🤝',
    color: 'var(--color-brand-peach)',
    accent: 'var(--color-brand-peach, #ffb084)',
    nameKey: 'learning.subject.personal_social',
  },
  // --- beijing-taxonomy subjects (zh-CN default deploy) ---
  ethics_law: {
    subject: 'ethics_law',
    terrain: 'social',
    icon: '⚖️',
    color: 'var(--color-brand-ochre)',
    accent: 'var(--color-brand-ochre, #e8b94a)',
    nameKey: 'learning.subject.ethics_law',
  },
  general_technology: {
    subject: 'general_technology',
    terrain: 'science',
    icon: '⚙️',
    color: 'var(--color-brand-teal)',
    accent: 'var(--color-brand-mint, #a4d4c5)',
    nameKey: 'learning.subject.general_technology',
  },
  pe_health: {
    subject: 'pe_health',
    terrain: 'arts',
    icon: '🏃',
    color: 'var(--color-brand-coral)',
    accent: 'var(--color-brand-peach, #ffb084)',
    nameKey: 'learning.subject.pe_health',
  },
  labor: {
    subject: 'labor',
    terrain: 'arts',
    icon: '🛠',
    color: 'var(--color-brand-peach)',
    accent: 'var(--color-brand-peach, #ffb084)',
    nameKey: 'learning.subject.labor',
  },
  comprehensive_practical: {
    subject: 'comprehensive_practical',
    terrain: 'arts',
    icon: '🧩',
    color: 'var(--color-brand-pink)',
    accent: 'var(--color-brand-pink, #ff4d8b)',
    nameKey: 'learning.subject.comprehensive_practical',
  },
}

/** Default theme for unknown subjects */
export const DEFAULT_THEME: ContinentTheme = {
  subject: 'default',
  terrain: 'default',
  icon: '📚',
  color: 'var(--color-text-secondary)',
  accent: 'var(--color-surface-card)',
  nameKey: 'learning.subject.default',
}

/** Get the theme for a subject, falling back to default */
export function getContinentTheme(subject: string): ContinentTheme {
  return CONTINENT_THEMES[subject] ?? DEFAULT_THEME
}

/** Get the terrain class string for a subject */
export function getTerrainClass(subject: string): string {
  return `territory--${getContinentTheme(subject).terrain}`
}
