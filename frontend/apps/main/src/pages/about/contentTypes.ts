/**
 * Content types for About sub-pages (Terms, Privacy, etc.).
 *
 * i18n note: Legal document body text is stored as full structured content in
 * per-language data files (e.g. `data/terms-zh.ts`, `data/terms-en.ts`), selected
 * at runtime via `useLocalizedContent`. This bypasses the project's `t()` system
 * intentionally — ~1300 lines of legal prose per language would bloat locale JSON
 * and be difficult to maintain. See spec §3.4 for the design rationale.
 */

export type ContentBlock =
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] }

export interface ContentSection {
  heading: string
  blocks: ContentBlock[]
}
