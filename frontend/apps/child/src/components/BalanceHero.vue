<template>
  <div class="balance-hero" :class="variant" :data-reacting="reacting">
    <div class="balance-hero-total">
      <span class="balance-hero-num">{{ amount }}</span>
      <span class="balance-hero-star">⭐</span>
    </div>
    <div class="balance-hero-coins">
      <CoinDisplay
        :amount="amount"
        :icon-size="iconSize"
        :copper-to-silver="copperToSilver"
        :silver-to-gold="silverToGold"
        :animate-changes="animateChanges"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import CoinDisplay from '@/components/coins/CoinDisplay.vue'

withDefaults(
  defineProps<{
    amount: number
    /** Page background variant — keeps visual nav color per page. */
    variant?: 'home' | 'tasks' | 'wishes' | 'ledger'
    iconSize?: number
    copperToSilver?: number
    silverToGold?: number
    animateChanges?: boolean
    /** Optional pop/glow reaction (Tasks page balance bump on parent grant). */
    reacting?: 'pop' | 'invert' | null
  }>(),
  {
    variant: 'home',
    iconSize: 22,
    copperToSilver: 10,
    silverToGold: 10,
    animateChanges: false,
    reacting: null,
  },
)
</script>

<style scoped>
/* ── Base hero: total number (left) + coin tiers horizontal (right) ── */
.balance-hero {
  position: relative;
  border-radius: var(--radius-xl);
  padding: 24px 20px;
  margin-bottom: var(--space-lg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  /* Coin text defaults to ink so tiers read on any feature background */
  --coin-text-gold:   var(--color-ink);
  --coin-text-silver: var(--color-ink);
  --coin-text-copper: var(--color-ink);
  transition: box-shadow 300ms ease-out;
}

.balance-hero-total {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-family: Inter, sans-serif;
  line-height: 1;
}
.balance-hero-num {
  font-size: 32px;
  font-weight: 800;
  color: var(--color-brand-ochre);
  font-variant-numeric: tabular-nums;
}
.balance-hero-star {
  font-size: 22px;
}
.balance-hero-coins {
  flex-shrink: 0;
}

/* ── Variant backgrounds — per-page color nav ── */
.balance-hero.home {
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline-soft);
}
.balance-hero.tasks {
  background: linear-gradient(135deg, var(--color-brand-ochre), var(--color-brand-peach));
}
.balance-hero.wishes {
  background: var(--color-brand-peach);
}
.balance-hero.ledger {
  background: var(--color-brand-teal);
  color: var(--color-on-dark);
}

/* ── Dark mode ── */
[data-theme="dark"] .balance-hero.home {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02)),
    var(--color-surface-card);
  border-color: var(--color-hairline);
}
[data-theme="dark"] .balance-hero.home .balance-hero-num {
  color: var(--color-coin-gold-text);
}
[data-theme="dark"] .balance-hero.tasks {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-ochre-rgb), 0.16), rgba(var(--color-brand-peach-rgb), 0.10)),
    var(--color-surface-card);
}
[data-theme="dark"] .balance-hero.wishes {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-peach-rgb), 0.14), rgba(var(--color-brand-peach-rgb), 0.06)),
    var(--color-surface-card);
}
[data-theme="dark"] .balance-hero.ledger {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-mint-rgb), 0.14), rgba(var(--color-brand-mint-rgb), 0.06)),
    var(--color-surface-card);
  color: var(--color-on-feature-teal);
}

/* On colored feature backgrounds (tasks/wishes/ledger) the total num reads as ink */
.balance-hero.tasks .balance-hero-num,
.balance-hero.wishes .balance-hero-num,
.balance-hero.ledger .balance-hero-num {
  color: var(--color-ink);
}
[data-theme="dark"] .balance-hero.tasks .balance-hero-num,
[data-theme="dark"] .balance-hero.wishes .balance-hero-num,
[data-theme="dark"] .balance-hero.ledger .balance-hero-num {
  color: var(--color-on-feature-ochre);
}
/* Ledger (teal) needs light text in light mode for contrast */
.balance-hero.ledger .balance-hero-num {
  color: var(--color-on-dark);
}
.balance-hero.ledger .balance-hero-star {
  color: var(--color-on-dark);
}

/* Dark-mode coin text: each variant warms its coin numerals to match the
   tinted surface (matches pre-refactor Tasks/Ledger behavior). */
[data-theme="dark"] .balance-hero.tasks {
  --coin-text-gold:   var(--color-on-feature-ochre);
  --coin-text-silver: var(--color-on-feature-ochre);
  --coin-text-copper: var(--color-on-feature-ochre);
}
[data-theme="dark"] .balance-hero.ledger {
  --coin-text-gold:   var(--color-on-feature-teal);
  --coin-text-silver: var(--color-on-feature-teal);
  --coin-text-copper: var(--color-on-feature-teal);
}
[data-theme="dark"] .balance-hero.ledger .balance-hero-num,
[data-theme="dark"] .balance-hero.ledger .balance-hero-star {
  color: var(--color-on-feature-teal);
}

/* Dark-mode coin legibility on deep feature surfaces */
[data-theme="dark"] .balance-hero :deep(.coin-display) {
  padding: 4px 8px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
[data-theme="dark"] .balance-hero :deep(svg) {
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.45));
}

/* ── Tasks reaction: pop + glow on parent grant ── */
.balance-hero[data-reacting='pop'] {
  animation: balance-pop 250ms cubic-bezier(0.175, 0.885, 0.32, 1.275),
             balance-glow 1500ms ease-out;
  box-shadow: 0 0 40px rgba(232, 185, 74, 0.6);
}
.balance-hero[data-reacting='invert'] {
  animation: balance-color-invert 400ms ease-out;
}
@keyframes balance-pop {
  0% { transform: scale(1); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); }
}
@keyframes balance-glow {
  0%   { box-shadow: 0 0 0 rgba(232, 185, 74, 0); }
  20%  { box-shadow: 0 0 48px rgba(232, 185, 74, 0.75); }
  60%  { box-shadow: 0 0 32px rgba(232, 185, 74, 0.55); }
  100% { box-shadow: 0 0 0 rgba(232, 185, 74, 0); }
}
@keyframes balance-color-invert {
  0% { filter: hue-rotate(0); }
  50% { filter: hue-rotate(60deg) brightness(1.1); }
  100% { filter: hue-rotate(0); }
}
</style>
