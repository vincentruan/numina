/**
 * Continent themes — visual identity for each subject area.
 *
 * Main-app version with hex colors (self-contained, no Clay token dependency).
 * Used by ParentKnowledgeCastle for tower theming.
 *
 * Original: apps/child/src/data/continentThemes.ts — this copy carries only the
 * fields the parent castle reads (icon/color/accent). Subject *labels* come
 * from `@/utils/domainLabel` subjectLabel, not from here.
 */

export interface ContinentTheme {
  icon: string
  color: string
  accent: string
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
  mathematics: { icon: '📐', color: OCHRE, accent: OCHRE_LIGHT },
  science: { icon: '🔬', color: TEAL, accent: TEAL_LIGHT },
  chinese: { icon: '📖', color: CORAL, accent: CORAL_LIGHT },
  english: { icon: '🔤', color: LAVENDER, accent: LAVENDER_LIGHT },
  physics: { icon: '⚡', color: TEAL, accent: TEAL_LIGHT },
  chemistry: { icon: '🧪', color: SAGE, accent: SAGE_LIGHT },
  biology: { icon: '🌿', color: SAGE, accent: SAGE_LIGHT },
  history: { icon: '📜', color: OCHRE, accent: OCHRE_LIGHT },
  geography: { icon: '🌍', color: SAGE, accent: SAGE_LIGHT },
  politics: { icon: '🏛', color: LAVENDER, accent: LAVENDER_LIGHT },
  art: { icon: '🎨', color: CORAL, accent: CORAL_LIGHT },
  music: { icon: '🎵', color: LAVENDER, accent: LAVENDER_LIGHT },
  physical_education: { icon: '🏃', color: TEAL, accent: TEAL_LIGHT },
  information_technology: { icon: '💻', color: TEAL, accent: TEAL_LIGHT },
  computing: { icon: '🖥', color: TEAL, accent: MINT },
  learning_to_learn: { icon: '🧠', color: LAVENDER, accent: LAVENDER },
  life_skills: { icon: '🧺', color: MINT, accent: MINT },
  personal_social: { icon: '🤝', color: PEACH, accent: PEACH },
  ethics_law: { icon: '⚖️', color: OCHRE, accent: OCHRE },
  general_technology: { icon: '⚙️', color: TEAL, accent: MINT },
  pe_health: { icon: '🏃', color: CORAL, accent: PEACH },
  labor: { icon: '🛠', color: PEACH, accent: PEACH },
  comprehensive_practical: { icon: '🧩', color: PINK, accent: PINK },
}

export const DEFAULT_THEME: ContinentTheme = {
  icon: '📚',
  color: '#616161',
  accent: '#f5f5ff',
}

export function getContinentTheme(subject: string): ContinentTheme {
  return CONTINENT_THEMES[subject] ?? DEFAULT_THEME
}
