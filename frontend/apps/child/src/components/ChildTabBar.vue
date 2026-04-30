<template>
  <div class="tab-bar-wrapper">
    <van-tabbar route>
      <van-tabbar-item to="/child/" icon="home-o">首页</van-tabbar-item>
      <van-tabbar-item to="/child/wishes" icon="star-o">心愿</van-tabbar-item>
      <van-tabbar-item to="/child/tasks" icon="todo-list-o">任务</van-tabbar-item>
      <van-tabbar-item to="/child/treasures" icon="gift-o">我的宝贝</van-tabbar-item>
      <van-tabbar-item to="/child/ledger" icon="bill-o">账本</van-tabbar-item>
    </van-tabbar>

    <!-- Dark mode toggle — floats above tab bar -->
    <button
      class="theme-toggle"
      :aria-label="isDark ? '切换到日间模式' : '切换到夜间模式'"
      @click="toggle"
    >
      {{ isDark ? '☀️' : '🌙' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { useDarkMode } from '@/utils/darkMode'

const { isDark, toggle } = useDarkMode()
</script>

<style scoped>
.tab-bar-wrapper {
  position: relative;
}

.theme-toggle {
  position: fixed;
  bottom: 68px;
  right: 16px;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-pill);
  background: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 100;
  transition: transform 0.15s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.theme-toggle:active {
  transform: scale(0.9);
}
</style>
