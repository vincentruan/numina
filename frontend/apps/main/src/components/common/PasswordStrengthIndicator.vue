<template>
  <div v-if="password" class="password-strength">
    <div class="strength-bars">
      <div
        v-for="i in 4"
        :key="i"
        class="strength-bar"
        :class="{ active: i <= strengthLevel }"
      />
    </div>
    <span class="strength-label" :class="strengthClass">{{ strengthText }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  password: string
}>()

const { t } = useI18n()

// Password strength calculation
const strengthLevel = computed(() => {
  const pwd = props.password
  if (!pwd) return 0

  let score = 0

  // Length check
  if (pwd.length >= 6) score += 1
  if (pwd.length >= 8) score += 1
  if (pwd.length >= 12) score += 1

  // Character variety
  if (/[a-z]/.test(pwd)) score += 1
  if (/[A-Z]/.test(pwd)) score += 1
  if (/[0-9]/.test(pwd)) score += 1
  if (/[^a-zA-Z0-9]/.test(pwd)) score += 1

  // Normalize to 1-4 levels
  if (score <= 2) return 1 // Weak
  if (score <= 4) return 2 // Fair
  if (score <= 5) return 3 // Good
  return 4 // Strong
})

const strengthClass = computed(() => {
  const level = strengthLevel.value
  if (level === 1) return 'weak'
  if (level === 2) return 'fair'
  if (level === 3) return 'good'
  return 'strong'
})

const strengthText = computed(() => {
  const level = strengthLevel.value
  if (level === 1) return t('passwordStrength.weak')
  if (level === 2) return t('passwordStrength.fair')
  if (level === 3) return t('passwordStrength.good')
  return t('passwordStrength.strong')
})
</script>

<style scoped>
.password-strength {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  padding: 0 16px;
}
.strength-bars {
  display: flex;
  gap: 3px;
}
.strength-bar {
  width: 16px;
  height: 3px;
  background: var(--separator);
  border-radius: 2px;
  transition: background 0.3s;
}
.strength-bar.active {
  background: currentColor;
}
.strength-label {
  font-size: 12px;
}
.strength-label.weak {
  color: #ee0a24;
}
.strength-bar.active ~ .strength-bar.active {
  color: inherit;
}
.strength-bars:has(.active) .strength-bar.active {
  color: #ee0a24;
}
/* When 2+ bars active, change to orange */
.strength-bars:has(.active:nth-child(2)) .strength-bar.active {
  color: #ff976a;
}
/* When 3+ bars active, change to primary */
.strength-bars:has(.active:nth-child(3)) .strength-bar.active {
  color: var(--color-action-blue);
}
/* When 4 bars active, change to green */
.strength-bars:has(.active:nth-child(4)) .strength-bar.active {
  color: #07c160;
}
.strength-label.fair {
  color: #ff976a;
}
.strength-label.good {
  color: var(--color-action-blue);
}
.strength-label.strong {
  color: #07c160;
}
</style>