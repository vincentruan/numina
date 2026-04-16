<template>
  <Teleport to="body">
    <div v-if="visible" class="milestone-overlay" @click="dismiss">
      <div class="confetti-container">
        <span v-for="i in 20" :key="i" class="confetti" :style="confettiStyle(i)" />
      </div>
      <div class="milestone-card">
        <div class="milestone-icon">{{ icon }}</div>
        <div class="milestone-title">{{ title }}</div>
        <div class="milestone-desc">{{ desc }}</div>
        <button class="dismiss-btn" @click.stop="dismiss">太棒了！</button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MilestoneType } from '@/api/milestones'

const props = defineProps<{
  visible: boolean
  milestoneType: MilestoneType | string  // string fallback for future types
}>()

const emit = defineEmits<{ (e: 'dismiss'): void }>()

function dismiss() {
  emit('dismiss')
}

const MILESTONE_META: Record<string, { icon: string; title: string; desc: string }> = {
  first_chore:        { icon: '🌟', title: '第一个家务！',     desc: '你完成了人生第一个家务，太棒了！' },
  first_wish_realized:{ icon: '🎁', title: '第一个心愿实现！', desc: '你的努力换来了心愿成真！' },
  coins_50:           { icon: '💰', title: '攒到50颗星星币！', desc: '继续加油，更多心愿等着你！' },
  coins_200:          { icon: '🏆', title: '攒到200颗星星币！',desc: '你是理财小达人！' },
  streak_7:           { icon: '🔥', title: '连续打卡7天！',    desc: '一周不间断，获得1.5倍奖励！' },
  streak_14:          { icon: '🔥🔥', title: '连续打卡14天！', desc: '两周坚持，获得2倍奖励！' },
  streak_30:          { icon: '👑', title: '连续打卡30天！',   desc: '一个月的坚持，你是冠军！' },
}

const meta = computed(() => MILESTONE_META[props.milestoneType] ?? { icon: '🎉', title: '新成就！', desc: '恭喜你解锁了新成就！' })
const icon = computed(() => meta.value.icon)
const title = computed(() => meta.value.title)
const desc = computed(() => meta.value.desc)

const COLORS = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff', '#ff922b', '#cc5de8']

function confettiStyle(i: number) {
  const color = COLORS[i % COLORS.length]
  const left = ((i * 37 + 11) % 100)
  const delay = ((i * 0.15) % 1.5).toFixed(2)
  const size = 8 + (i % 5) * 2
  return {
    left: `${left}%`,
    animationDelay: `${delay}s`,
    background: color,
    width: `${size}px`,
    height: `${size}px`,
  }
}
</script>

<style scoped>
.milestone-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}
.confetti-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.confetti {
  position: absolute;
  top: -10px;
  border-radius: 2px;
  animation: fall 2s ease-in forwards;
}
@keyframes fall {
  0%   { transform: translateY(0) rotate(0deg); opacity: 1; }
  100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
}
.milestone-card {
  background: #fff;
  border-radius: 20px;
  padding: 32px 28px;
  text-align: center;
  max-width: 300px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0,0,0,0.25);
  position: relative;
  z-index: 1;
}
.milestone-icon { font-size: 56px; margin-bottom: 12px; }
.milestone-title { font-size: 22px; font-weight: 800; color: #333; margin-bottom: 8px; }
.milestone-desc { font-size: 15px; color: #666; margin-bottom: 24px; line-height: 1.5; }
.dismiss-btn {
  background: linear-gradient(135deg, #f5a623, #ff6d00);
  color: #fff;
  border: none;
  border-radius: 24px;
  padding: 12px 32px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}
</style>
