<template>
  <div
    v-if="props.members.length || props.familyName"
    class="family-crest"
    :class="{ 'family-crest--revealed': revealed }"
    role="img"
    :aria-label="crestAriaLabel"
  >
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <!-- Connecting ring -->
      <circle
        cx="50" cy="50" r="35"
        fill="none"
        stroke="var(--ceremony-gold, #c9a84c)"
        stroke-width="1"
        opacity="0.4"
      />
      <!-- Member initials around the ring -->
      <g
        v-for="(pos, idx) in memberPositions"
        :key="idx"
        class="family-crest__member"
        :class="pos.isActive ? 'family-crest__member--active' : 'family-crest__member--muted'"
        :transform="`translate(${pos.x}, ${pos.y})`"
      >
        <circle r="10" />
        <text
          font-size="10"
          text-anchor="middle"
          dominant-baseline="central"
        >{{ pos.initial }}</text>
      </g>
    </svg>
    <!-- Family character overlay -->
    <span class="family-crest__center">{{ sealChar }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

defineOptions({ name: 'FamilyCrest' })

const { t } = useI18n()

interface MemberInfo {
  name: string
  role: string
  signingStatus?: 'signed' | 'confirmed' | 'pending_sign' | 'pending_confirm' | 'rejected' | 'expired'
  signedDate?: string
}

const props = defineProps<{
  members: MemberInfo[]
  familyName: string
}>()

const RING_RADIUS = 35
const CENTER = 50

/** Family character with multi-level fallback (KTD3) */
const sealChar = computed(() => {
  const fromFamily = props.familyName.trim().charAt(0)
  if (fromFamily) return fromFamily
  const fromMember = props.members[0]?.name.trim().charAt(0)
  if (fromMember) return fromMember
  return '家'
})

/** Trigonometric positioning for members on the ring (KTD4) */
const memberPositions = computed(() => {
  const n = props.members.length
  if (n === 0) return []

  return props.members.map((member, i) => {
    const theta = (2 * Math.PI * i) / n - Math.PI / 2
    const x = CENTER + RING_RADIUS * Math.cos(theta)
    const y = CENTER + RING_RADIUS * Math.sin(theta)
    const isActive = member.signingStatus === 'signed' || member.signingStatus === 'confirmed'
    const initial = member.name.trim().charAt(0) || '?'
    return { member, x, y, isActive, initial }
  })
})

/** Aria label describing crest state (i18n) */
const crestAriaLabel = computed(() => {
  const total = props.members.length
  const signedCount = props.members.filter(
    m => m.signingStatus === 'signed' || m.signingStatus === 'confirmed',
  ).length
  return t('manifesto.crestAria', { name: sealChar.value, signed: signedCount, total })
})

// Entrance animation (double-rAF, mirrors WaxSeal pattern)
const revealed = ref(false)
let rafId = 0

onMounted(() => {
  if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    revealed.value = true
    return
  }
  rafId = requestAnimationFrame(() => {
    rafId = requestAnimationFrame(() => {
      revealed.value = true
    })
  })
})

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
})
</script>

<style scoped>
.family-crest {
  width: clamp(80px, 18vw, 96px);
  height: auto;
  margin: 0 auto 0.75rem;
  display: block;
  position: relative;
  /* Entrance animation initial state */
  opacity: 0;
  transform: scale(0.9);
  transition: opacity 0.4s ease-out, transform 0.4s ease-out;
}

.family-crest--revealed {
  opacity: 1;
  transform: scale(1);
}

.family-crest svg {
  width: 100%;
  height: auto;
  display: block;
}

.family-crest__center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: clamp(20px, 6vw, 26px);
  font-family: 'Noto Serif SC', 'STSong', 'SimSun', 'Songti SC', serif;
  font-weight: 900;
  color: var(--ceremony-gold, #c9a84c);
  line-height: 1;
  user-select: none;
  pointer-events: none;
}

/* ── Member signing states (KTD5) ── */
.family-crest__member {
  transition: opacity 0.3s ease-out, transform 0.3s ease-out;
}

.family-crest__member--active {
  transform: scale(1);
  opacity: 1;
}

.family-crest__member--active circle {
  fill: var(--ceremony-gold, #c9a84c);
}

.family-crest__member--active text {
  fill: #fff;
}

.family-crest__member--muted {
  transform: scale(0.9);
  opacity: 0.5;
}

.family-crest__member--muted circle {
  fill: var(--ceremony-ink, #1a1a2e);
  opacity: 0.5;
}

.family-crest__member--muted text {
  fill: var(--ceremony-gold, #c9a84c);
}

/* ── Dark mode ── */
:global([data-theme='dark']) .family-crest__member--muted circle {
  fill: var(--ceremony-ink-dark, #f0ece4);
  opacity: 0.45;
}

:global([data-theme='dark']) .family-crest__member--muted text {
  fill: var(--ceremony-ink-dark, #f0ece4);
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
  .family-crest {
    opacity: 1;
    transform: scale(1);
    transition: none;
  }

  .family-crest__member {
    transition: none;
  }
}
</style>
