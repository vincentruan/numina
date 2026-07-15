import { describe, it, expect } from 'vitest'
import { extractCitationSources } from '../citations'

describe('citations', () => {
  describe('extractCitationSources', () => {
    it('should extract single citation', () => {
      const markdown = 'According to [citation: Example](https://example.com), the data shows...'
      const sources = extractCitationSources(markdown)

      expect(sources).toHaveLength(1)
      expect(sources[0].url).toBe('https://example.com/')
      expect(sources[0].title).toBe('Example')
      expect(sources[0].domain).toBe('example.com')
      expect(sources[0].count).toBe(1)
    })

    it('should group citations by URL', () => {
      const markdown = `
        First mention [citation: Example](https://example.com)
        Second mention [citation: Example Again](https://example.com)
      `
      const sources = extractCitationSources(markdown)

      expect(sources).toHaveLength(1)
      expect(sources[0].count).toBe(2)
      expect(sources[0].occurrences).toHaveLength(2)
    })

    it('should handle multiple different URLs', () => {
      const markdown = `
        [citation: Site A](https://site-a.com)
        [citation: Site B](https://site-b.com)
        [citation: Site A again](https://site-a.com)
      `
      const sources = extractCitationSources(markdown)

      expect(sources).toHaveLength(2)
      const siteA = sources.find(s => s.domain === 'site-a.com')
      const siteB = sources.find(s => s.domain === 'site-b.com')

      expect(siteA?.count).toBe(2)
      expect(siteB?.count).toBe(1)
    })

    it('should replace generic titles with domain', () => {
      const markdown = '[citation: Source](https://example.com)'
      const sources = extractCitationSources(markdown)

      expect(sources[0].title).toBe('example.com')
    })

    it('should ignore image links', () => {
      const markdown = '![citation: Image](https://example.com/img.png)'
      const sources = extractCitationSources(markdown)

      expect(sources).toHaveLength(0)
    })

    it('should mask code blocks', () => {
      const markdown = `
        Real citation [citation: Real](https://real.com)

        \`\`\`
        [citation: Fake](https://fake.com)
        \`\`\`
      `
      const sources = extractCitationSources(markdown)

      expect(sources).toHaveLength(1)
      expect(sources[0].domain).toBe('real.com')
    })

    it('should handle empty input', () => {
      expect(extractCitationSources('')).toHaveLength(0)
      expect(extractCitationSources('No citations here')).toHaveLength(0)
    })
  })
})
