// contentTypes.ts — shared types for all about sub-pages

export type ContentBlock =
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] }

export interface ContentSection {
  heading: string
  blocks: ContentBlock[]
}
