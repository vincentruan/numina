/**
 * Slash skill detection utilities
 *
 * Mirrors DeerFlow's slash parser (deerflow/skills/slash.py) for frontend use.
 * Used by InputBox to detect slash commands and show autocomplete.
 */

/** Regex for valid slash skill names: lowercase letters, digits, hyphens */
const SLASH_SKILL_REGEX = /^\/([a-z0-9-]+)(?:\s+(.*))?$/

/** Reserved command names (DeerFlow TUI commands, not user-facing skills) */
const RESERVED_COMMANDS = new Set([
  'bootstrap',
  'goal',
  'help',
  'memory',
  'models',
  'new',
  'status',
])

/**
 * Parse a slash command from user input
 *
 * @param text - User input text
 * @returns Parsed slash command or null if not a valid slash command
 */
export function parseSlashCommand(text: string): { skillId: string; args: string } | null {
  const trimmed = text.trim()
  if (!trimmed.startsWith('/')) {
    return null
  }

  const match = trimmed.match(SLASH_SKILL_REGEX)
  if (!match) {
    return null
  }

  const skillId = match[1]
  const args = match[2] || ''

  // Reject reserved commands
  if (RESERVED_COMMANDS.has(skillId)) {
    return null
  }

  return { skillId, args }
}

/**
 * Check if text is a partial slash command (for autocomplete trigger)
 *
 * @param text - User input text
 * @returns true if text starts with / and contains a valid skill name prefix
 */
export function isPartialSlashCommand(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed.startsWith('/')) {
    return false
  }

  // Must have at least one character after /
  const afterSlash = trimmed.slice(1)
  if (!afterSlash || /\s/.test(afterSlash)) {
    return false
  }

  // Must match the skill name pattern (no spaces yet)
  return /^[a-z0-9-]+$/.test(afterSlash)
}

/**
 * Extract the skill name prefix from partial slash command
 *
 * @param text - User input text
 * @returns Skill name prefix or null
 */
export function extractSkillPrefix(text: string): string | null {
  if (!isPartialSlashCommand(text)) {
    return null
  }

  return text.trim().slice(1)
}
