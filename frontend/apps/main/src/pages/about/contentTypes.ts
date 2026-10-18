// contentTypes.ts — shared types for all about sub-pages

export interface ContentBlock {
  type: 'paragraph' | 'list'
  text?: string
  items?: string[]
}

export interface ContentSection {
  heading: string
  blocks: ContentBlock[]
}
