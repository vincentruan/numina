<template>
  <div class="deployment-heatmap">
    <van-grid :column-num="columnNum" class="heatmap-grid">
      <van-grid-item
        v-for="opt in options"
        :key="opt.method"
        class="heatmap-cell"
        :class="`difficulty-${opt.difficulty}`"
      >
        <div class="cell-content">
          <span class="method-name">{{ opt.method }}</span>
          <span class="time-estimate">{{ opt.time }}</span>
        </div>
      </van-grid-item>
    </van-grid>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface DeploymentOption {
  method: string
  time: string
  difficulty: 'easy' | 'medium' | 'hard'
}

interface Props {
  options?: DeploymentOption[]
  columnNum?: number
}

const props = withDefaults(defineProps<Props>(), {
  options: () => [
    { method: 'Docker Compose', time: '10 分钟', difficulty: 'easy' },
    { method: '手动部署', time: '30 分钟', difficulty: 'medium' },
    { method: '云服务器', time: '2 小时', difficulty: 'hard' }
  ],
  columnNum: 2
})
</script>

<style scoped>
.deployment-heatmap {
  width: 100%;
}

.heatmap-grid {
  border-radius: 12px;
  overflow: hidden;
}

.heatmap-cell {
  padding: 16px;
}

.cell-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: center;
}

.method-name {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
}

.time-estimate {
  font-size: 14px;
  color: #6e6e73;
}

/* Difficulty color coding */
.difficulty-easy {
  background: #e8f5e9;
  border-left: 4px solid #4caf50;
}

.difficulty-medium {
  background: #fff8e1;
  border-left: 4px solid #ffc107;
}

.difficulty-hard {
  background: #ffebee;
  border-left: 4px solid #f44336;
}

/* Desktop: 3 columns */
@media (min-width: 768px) {
  .cell-content {
    gap: 12px;
  }

  .method-name {
    font-size: 18px;
  }

  .time-estimate {
    font-size: 16px;
  }
}
</style>