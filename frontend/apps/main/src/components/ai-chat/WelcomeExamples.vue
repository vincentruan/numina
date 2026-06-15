<script setup lang="ts">
/**
 * DeerFlow WelcomeExamples 组件
 *
 * 参考: frontend/src/components/workspace/input-box.tsx SuggestionList()
 *
 * 功能:
 * - 显示欢迎态的示例问题按钮
 * - 点击填充输入框并发送
 * - 包含 "Surprise Me" 按钮和预设建议列表
 * - 家庭资产规划场景专用建议
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import IIcon from '@/components/IIcon.vue'

const { t } = useI18n()

const emit = defineEmits<{
  select: [prompt: string]
  surprise: []
}>()

// 预设建议列表 - 家庭资产规划场景
const suggestions = computed(() => [
  {
    key: 'analyze',
    label: t('aiChat.welcomeExampleAnalyze'),
    prompt: t('aiChat.welcomeExampleAnalyzePrompt'),
    icon: 'chart-pie',
  },
  {
    key: 'plan',
    label: t('aiChat.welcomeExamplePlan'),
    prompt: t('aiChat.welcomeExamplePlanPrompt'),
    icon: 'lightbulb',
  },
  {
    key: 'learn',
    label: t('aiChat.welcomeExampleLearn'),
    prompt: t('aiChat.welcomeExampleLearnPrompt'),
    icon: 'graduation-cap',
  },
  {
    key: 'optimize',
    label: t('aiChat.welcomeExampleOptimize'),
    prompt: t('aiChat.welcomeExampleOptimizePrompt'),
    icon: 'target',
  },
])

function handleSuggestionClick(prompt: string) {
  emit('select', prompt)
}

function handleSurprise() {
  emit('surprise')
}
</script>

<template>
  <div class="welcome-examples">
    <!-- Surprise Me 按钮 (DeerFlow pattern) -->
    <button
      class="example-btn surprise-btn"
      @click="handleSurprise"
    >
      <IIcon icon="sparkles" class="btn-icon" />
      <span class="btn-label">{{ t('aiChat.welcomeExampleSurprise') }}</span>
    </button>

    <!-- 建议按钮列表 -->
    <button
      v-for="suggestion in suggestions"
      :key="suggestion.key"
      class="example-btn"
      @click="handleSuggestionClick(suggestion.prompt)"
    >
      <IIcon :icon="suggestion.icon" class="btn-icon" />
      <span class="btn-label">{{ suggestion.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.welcome-examples {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  padding: 12px 0;
  width: 100%;
}

.example-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 44px; /* Touch target size - DeerFlow pattern */
}

.example-btn:hover {
  background: var(--card-bg);
  border-color: var(--van-primary-color);
  color: var(--van-primary-color);
}

.example-btn:active {
  transform: scale(0.98);
}

.surprise-btn {
  background: linear-gradient(135deg, var(--van-primary-color) 0%, #a07cfe 100%);
  border-color: transparent;
  color: white;
}

.surprise-btn:hover {
  opacity: 0.9;
  color: white;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.btn-label {
  font-weight: 500;
}

/* Stagger animation (DeerFlow pattern: 60ms delay) */
.example-btn {
  opacity: 0;
  animation: fade-in-up 0.15s ease-out forwards;
}

.example-btn:nth-child(1) { animation-delay: 0ms; }
.example-btn:nth-child(2) { animation-delay: 60ms; }
.example-btn:nth-child(3) { animation-delay: 120ms; }
.example-btn:nth-child(4) { animation-delay: 180ms; }
.example-btn:nth-child(5) { animation-delay: 240ms; }

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 375px 响应式 */
@media (max-width: 375px) {
  .welcome-examples {
    gap: 6px;
    padding: 8px 0;
  }

  .example-btn {
    padding: 6px 12px;
    font-size: 12px;
    min-height: 36px;
  }

  .btn-icon {
    width: 14px;
    height: 14px;
  }
}
</style>