import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * A single chat slash command (local static — NOT from useCapabilityStore).
 *
 * `useCapabilityStore.capabilities` are routable features surfaced from
 * `/ai/capabilities`; chat commands like `/goal` and `/compact` are a
 * different concept (they are handled by the chat composer itself) and must
 * come from this local static registry. See plan risk #4.
 */
export interface SlashCommand {
  /** Command keyword including the leading slash, e.g. `/goal`. */
  name: string
  /** i18n-localized short description shown in the palette. */
  description: string
  /** The text to fill the textarea with when selected (without args). */
  insertText: string
  /**
   * Apply callback invoked on selection. Returns true when the command was
   * fully handled (the composer should NOT submit); false when the composer
   * should proceed to submit the (possibly rewritten) textarea value.
   *
   * U1 only wires the palette + selection mechanism; the actual goal/compact
   * logic lives in U2/U4/U5/U6, so the default callbacks here are stubs that
   * U5/U6 will replace/extend.
   */
  apply: (ctx: SlashCommandApplyContext) => boolean
}

export interface SlashCommandApplyContext {
  /** Current textarea value (trimmed). */
  value: string
  /** Replace the textarea value. */
  setValue: (next: string) => void
}

/**
 * Local static registry of chat slash commands. UI strings flow through i18n
 * (`slashGoalDesc`/`slashCompactDesc` under the `aiChat` namespace).
 */
export function useSlashCommands() {
  const { t } = useI18n()
  const query = ref('')

  const commands = computed<SlashCommand[]>(() => [
    {
      name: '/goal',
      description: t('aiChat.slashGoalDesc'),
      insertText: '/goal ',
      apply: (ctx) => {
        // U1 stub: U5 wires the real goal flow (set/status/clear).
        // For now, ensure the `/goal ` prefix is present so the user can type
        // the objective inline, then leave submission to the composer.
        if (!ctx.value.startsWith('/goal')) {
          ctx.setValue('/goal ')
        }
        return false
      },
    },
    {
      name: '/compact',
      description: t('aiChat.slashCompactDesc'),
      insertText: '/compact',
      apply: () => {
        // U1 stub: U6 wires the real compact flow + transient bridge.
        return true
      },
    },
  ])

  /** Commands filtered by the current `/query` prefix (case-insensitive). */
  const filteredCommands = computed(() => {
    const q = query.value.trim().toLowerCase()
    if (!q) return commands.value
    return commands.value.filter((c) => c.name.toLowerCase().startsWith(q))
  })

  return {
    commands,
    filteredCommands,
    query,
  }
}
