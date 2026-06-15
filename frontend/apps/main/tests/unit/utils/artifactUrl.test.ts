/**
 * artifactUrl.ts unit tests — URL encoding + tenant routing parity
 *
 * 参考: frontend/src/core/artifacts/utils.ts urlOfArtifact()
 */
import { describe, it, expect } from 'vitest'
import {
  urlOfArtifact,
  artifactContentUrl,
  artifactDownloadUrl,
  artifactOpenUrl,
} from '@/utils/ai-chat/artifactUrl'

describe('urlOfArtifact', () => {
  it('builds path with /ai/sessions prefix', () => {
    const url = urlOfArtifact('plan.md', 'sess-1')
    expect(url).toContain('/ai/sessions/sess-1/artifacts/plan.md')
  })

  it('encodes special characters in filepath', () => {
    const url = urlOfArtifact('foo bar/包/中文.md', 'sess-1')
    expect(url).toContain('/ai/sessions/sess-1/artifacts/')
    // spaces and slashes encoded
    expect(url).toContain('foo%20bar%2F')
    // Chinese encoded
    expect(url).toMatch(/%[0-9A-F]{2}/)
  })

  it('encodes querystring-dangerous characters', () => {
    const url = urlOfArtifact('a?b&c=1.txt', 'sess-1')
    expect(url).not.toContain('?b&c=1.txt')
    expect(url).toContain('a%3Fb%26c%3D1.txt')
  })

  it('appends ?download=true when download=true', () => {
    const url = urlOfArtifact('file.txt', 'sess-1', true)
    expect(url.endsWith('?download=true')).toBe(true)
  })

  it('omits download flag by default', () => {
    const url = urlOfArtifact('file.txt', 'sess-1')
    expect(url).not.toContain('download=true')
  })
})

describe('artifactContentUrl / artifactOpenUrl / artifactDownloadUrl', () => {
  it('artifactContentUrl == artifactOpenUrl (same URL, no download flag)', () => {
    const a = artifactContentUrl('file.txt', 'sess-1')
    const b = artifactOpenUrl('file.txt', 'sess-1')
    expect(a).toBe(b)
    expect(a).not.toContain('download=true')
  })

  it('artifactDownloadUrl appends ?download=true', () => {
    const url = artifactDownloadUrl('file.txt', 'sess-1')
    expect(url).toContain('?download=true')
  })

  it('Chinese path round-trips through encoding', () => {
    const url = artifactDownloadUrl('家庭资产报告.md', 'sess-1')
    const match = url.match(/artifacts\/(.+?)\?/)
    expect(match).not.toBeNull()
    if (match) {
      expect(decodeURIComponent(match[1])).toBe('家庭资产报告.md')
    }
  })
})
