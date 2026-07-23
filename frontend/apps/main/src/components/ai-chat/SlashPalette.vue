<script setup lang="ts">
/**
 * Slash command palette for the live AI-chat InputBox.
 *
 * Ported from the deprecated `components/common/AIChatInput.vue` palette
 * template + selectCapability logic, but backed by the LOCAL static command
 * registry (`useSlashCommands`) instead of `useCapabilityStore` (those are
 * routable features from `/ai/capabilities`, not chat commands — plan risk #4).
 *
 * Keyboard navigation (ArrowUp/Down/Tab/Enter/Esc) is owned by the parent
 * InputBox (it intercepts `@keydown` on the textarea) which drives
 * `selectedIndex` + `selectIndex`. This component renders the list and emits
 * `select` on mouse interaction.
 */
import { useI18n } from 'vue-i18n'
import type { SlashCommand } from '@/composables/ai-chat/useSlashCommands'

defineProps<{
  open: boolean
  commands: SlashCommand[]
  selectedIndex: number
}>()

const emit = defineEmits<{
  select: [command: SlashCommand]
}>()

const { t } = useI18n()

function onSelect(cmd: SlashCommand) {
  emit('select', cmd)
}
</script>

<template>
  <transition name="slash-palette">
    <div
      v-if="open"
      id="slash-palette-list"
      class="slash-palette"
      role="menu"
      :aria-label="t('aiChat.slashPaletteHint')"
    >
      <div
        v-if="commands.length === 0"
        class="slash-palette__empty"
        role="menuitem"
        aria-disabled="true"
      >
        {{ t('aiChat.slashPaletteEmpty') }}
      </div>
      <button
        v-for="(cmd, idx) in commands"
        :id="`slash-cmd-${cmd.name}`"
        :key="cmd.name"
        class="slash-palette__item"
        :class="{ 'slash-palette__item--selected': idx === selectedIndex }"
        role="menuitem"
        :aria-current="idx === selectedIndex ? true : undefined"
        @mousedown.prevent="onSelect(cmd)"
      >
        <span class="slash-palette__name">{{ cmd.name }}</span>
        <span class="slash-palette__desc">{{ cmd.description }}</span>
      </button>
    </div>
  </transition>
</template>

<style scoped>
.slash-palette {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  background: var(--ai-panel-bg, #ffffff);
  border: 1px solid var(--ai-panel-border, rgba(0, 0, 0, 0.08));
  border-radius: 14px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  z-index: 999;
  max-height: 60vh;
  overflow-y: auto;
  min-width: 160px;
}

:global([data-theme='dark']) .slash-palette {
  background: var(--ai-panel-bg, #12122a);
  border-color: var(--ai-panel-border, rgba(255, 255, 255, 0.1));
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.slash-palette__empty {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--ai-panel-item-color, var(--text-secondary, #666666));
  cursor: default;
}

.slash-palette__item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--ai-panel-item-color, var(--text-secondary, #666666));
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}

.slash-palette__item:hover {
  background: var(--ai-panel-item-hover-bg, rgba(0, 0, 0, 0.03));
  color: var(--ai-panel-item-hover-color, var(--text-primary, #111111));
}

.slash-palette__item:active {
  transform: scale(0.98);
}

.slash-palette__item--selected {
  background: var(--ai-panel-item-hover-bg, rgba(0, 0, 0, 0.06));
  color: var(--ai-panel-item-hover-color, var(--text-primary, #111111));
}

:global([data-theme='dark']) .slash-palette__item {
  color: var(--ai-panel-item-color, rgba(255, 255, 255, 0.6));
}

:global([data-theme='dark']) .slash-palette__item:hover,
:global([data-theme='dark']) .slash-palette__item--selected {
  background: var(--ai-panel-item-hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--ai-panel-item-hover-color, rgba(255, 255, 255, 0.9));
}

.slash-palette__name {
  font-weight: 500;
  color: var(--ai-text-color, var(--text-primary, #111111));
}

:global([data-theme='dark']) .slash-palette__name {
  color: var(--ai-text-color, rgba(255, 255, 255, 0.9));
}

.slash-palette__desc {
  font-size: 11px;
  color: var(--ai-panel-item-color, var(--text-secondary, #666666));
  line-height: 1.3;
}

.slash-palette-enter-active,
.slash-palette-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.slash-palette-enter-from,
.slash-palette-leave-to {
  opacity: 0;
  transform: scale(0.92) translateY(4px);
}
</style>
