/**
 * Continent themes — visual identity for each subject area.
 *
 * Main-app version with hex colors (self-contained, no Clay token dependency).
 * Used by ParentKnowledgeCastle for tower theming.
 *
 * Original: apps/child/src/data/continentThemes.ts
 */

export type Terrain = 'math' | 'science' | 'language' | 'social' | 'arts' | 'default'

export interface ContinentTheme {
  subject: string
  terrain: Terrain
  icon: string
  color: string
  accent: string
  nameKey: string
}

// Hex palette matching Clay brand tokens (self-contained for main app)
const OCHRE = '#e8b94a'
const OCHRE_LIGHT = '#fef3d9'
const TEAL = '#2a9d8f'
const TEAL_LIGHT = '#e6f7f5'
const CORAL = '#ff6b5a'
const CORAL_LIGHT = '#fde8e4'
const LAVENDER = '#b8a4ed'
const LAVENDER_LIGHT = '#f0e6ff'
const SAGE = '#6b9f78'
const SAGE_LIGHT = '#e8f5e9'
const MINT = '#a4d4c5'
const PEACH = '#ffb084'
const PINK = '#ff4d8b'

export const CONTINENT_THEMES: Record<string, ContinentTheme> = {
  mathematics: {
    subject: 'mathematics',
    terrain: 'math',
    icon: '📐',
    color: OCHRE,
    accent: OCHRE_LIGHT,
    nameKey: 'learning.subject.mathematics',
  },
  science: {
    subject: 'science',
    terrain: 'science',
    icon: '🔬',
    color: TEAL,
    accent: TEAL_LIGHT,
    nameKey: 'learning.subject.science',
  },
  chinese: {
    subject: 'chinese',
    terrain: 'language',
    icon: '📖',
    color: CORAL,
    accent: CORAL_LIGHT,
    nameKey: 'learning.subject.chinese',
  },
  english: {
    subject: 'english',
    terrain: 'language',
    icon: '🔤',
    color: LAVENDER,
    accent: LAVENDER_LIGHT,
    nameKey: 'learning.subject.english',
  },
  physics: {
    subject: 'physics',
    terrain: 'science',
    icon: '⚡',
    color: TEAL,
    accent: TEAL_LIGHT,
    nameKey: 'learning.subject.physics',
  },
  chemistry: {
    subject: 'chemistry',
    terrain: 'science',
    icon: '🧪',
    color: SAGE,
    accent: SAGE_LIGHT,
    nameKey: 'learning.subject.chemistry',
  },
  biology: {
    subject: 'biology',
    terrain: 'science',
    icon: '🌿',
    color: SAGE,
    accent: SAGE_LIGHT,
    nameKey: 'learning.subject.biology',
  },
  history: {
    subject: 'history',
    terrain: 'social',
    icon: '📜',
    color: OCHRE,
    accent: OCHRE_LIGHT,
    nameKey: 'learning.subject.history',
  },
  geography: {
    subject: 'geography',
    terrain: 'social',
    icon: '🌍',
    color: SAGE,
    accent: SAGE_LIGHT,
    nameKey: 'learning.subject.geography',
  },
  politics: {
    subject: 'politics',
    terrain: 'social',
    icon: '🏛',
    color: LAVENDER,
    accent: LAVENDER_LIGHT,
    nameKey: 'learning.subject.politics',
  },
  art: {
    subject: 'art',
    terrain: 'arts',
    icon: '🎨',
    color: CORAL,
    accent: CORAL_LIGHT,
    nameKey: 'learning.subject.art',
  },
  music: {
    subject: 'music',
    terrain: 'arts',
    icon: '🎵',
    color: LAVENDER,
    accent: LAVENDER_LIGHT,
    nameKey: 'learning.subject.music',
  },
  physical_education: {
    subject: 'physical_education',
    terrain: 'arts',
    icon: '🏃',
    color: TEAL,
    accent: TEAL_LIGHT,
    nameKey: 'learning.subject.physical_education',
  },
  information_technology: {
    subject: 'information_technology',
    terrain: 'science',
    icon: '💻',
    color: TEAL,
    accent: TEAL_LIGHT,
    nameKey: 'learning.subject.information_technology',
  },
  computing: {
    subject: 'computing',
    terrain: 'science',
    icon: '🖥',
    color: TEAL,
    accent: MINT,
    nameKey: 'learning.subject.computing',
  },
  learning_to_learn: {
    subject: 'learning_to_learn',
    terrain: 'social',
    icon: '🧠',
    color: LAVENDER,
    accent: LAVENDER,
    nameKey: 'learning.subject.learning_to_learn',
  },
  life_skills: {
    subject: 'life_skills',
    terrain: 'arts',
    icon: '🧺',
    color: MINT,
    accent: MINT,
    nameKey: 'learning.subject.life_skills',
  },
  personal_social: {
    subject: 'personal_social',
    terrain: 'social',
    icon: '🤝',
    color: PEACH,
    accent: PEACH,
    nameKey: 'learning.subject.personal_social',
  },
  ethics_law: {
    subject: 'ethics_law',
    terrain: 'social',
    icon: '⚖️',
    color: OCHRE,
    accent: OCHRE,
    nameKey: 'learning.subject.ethics_law',
  },
  general_technology: {
    subject: 'general_technology',
    terrain: 'science',
    icon: '⚙️',
    color: TEAL,
    accent: MINT,
    nameKey: 'learning.subject.general_technology',
  },
  pe_health: {
    subject: 'pe_health',
    terrain: 'arts',
    icon: '🏃',
    color: CORAL,
    accent: PEACH,
    nameKey: 'learning.subject.pe_health',
  },
  labor: {
    subject: 'labor',
    terrain: 'arts',
    icon: '🛠',
    color: PEACH,
    accent: PEACH,
    nameKey: 'learning.subject.labor',
  },
  comprehensive_practical: {
    subject: 'comprehensive_practical',
    terrain: 'arts',
    icon: '🧩',
    color: PINK,
    accent: PINK,
    nameKey: 'learning.subject.comprehensive_practical',
  },
}

export const DEFAULT_THEME: ContinentTheme = {
  subject: 'default',
  terrain: 'default',
  icon: '📚',
  color: '#616161',
  accent: '#f5f5ff',
  nameKey: 'learning.subject.default',
}

export function getContinentTheme(subject: string): ContinentTheme {
  return CONTINENT_THEMES[subject] ?? DEFAULT_THEME
}
