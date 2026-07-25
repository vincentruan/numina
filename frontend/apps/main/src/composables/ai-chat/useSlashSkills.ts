/**
 * Composable for managing slash-activated skills
 *
 * Fetches enabled custom skills from the backend and provides filtering
 * for autocomplete. Used by InputBox to show skill suggestions.
 */

import { ref } from 'vue'
import { getSkillsGrouped } from '@/api/ai'
import { extractSkillPrefix } from '@/utils/slashSkill'

export interface Skill {
  id: string
  name: string
  description?: string
  icon?: string
  color?: string
}

/**
 * Manage slash skill autocomplete
 *
 * @returns Composable state and methods
 */
export function useSlashSkills() {
  const skills = ref<Skill[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /**
   * Fetch enabled custom skills from backend
   */
  async function fetchSkills() {
    loading.value = true
    error.value = null

    try {
      const response = await getSkillsGrouped()
      // Filter to custom skills only (Q1 resolution: custom-skills-only)
      skills.value = response.custom
        .filter((s) => s.is_enabled)
        .map((s) => ({
          id: s.id,
          name: s.name || s.id,
          description: s.description,
          icon: s.icon,
          color: s.color,
        }))
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch skills'
      skills.value = []
    } finally {
      loading.value = false
    }
  }

  /**
   * Filter skills by prefix (for autocomplete)
   *
   * @param text - User input text
   * @returns Filtered skills matching the prefix
   */
  function filterSkills(text: string): Skill[] {
    const prefix = extractSkillPrefix(text)
    if (!prefix) {
      return []
    }

    const lowerPrefix = prefix.toLowerCase()
    return skills.value.filter(
      (skill) =>
        skill.id.toLowerCase().startsWith(lowerPrefix) ||
        skill.name.toLowerCase().startsWith(lowerPrefix)
    )
  }

  /**
   * Format a skill insertion (adds trailing space)
   *
   * @param skillId - Skill ID to insert
   * @returns Formatted text with trailing space
   */
  function formatSkillInsertion(skillId: string): string {
    return `/${skillId} `
  }

  return {
    skills,
    loading,
    error,
    fetchSkills,
    filterSkills,
    formatSkillInsertion,
  }
}
