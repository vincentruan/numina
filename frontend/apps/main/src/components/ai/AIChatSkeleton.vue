<script setup lang="ts">
/**
 * AIChatSkeleton - AI 对话页面骨架屏
 *
 * 在从 /ai 页面跳转到 /ai/chat 页面时，显示模拟对话界面的骨架屏，
 * 缓解线程创建和 SSE 连接建立期间的空白等待感。
 *
 * 参考 AIHubSkeleton 和 NProgress 处理逻辑：
 * - 路由 meta.hasSkeleton 立即完成 NProgress
 * - 骨架屏接管视觉反馈直到真实内容就绪
 */
</script>

<template>
  <div class="ai-chat-skeleton">
    <!-- Header skeleton -->
    <div class="chat-header-skeleton">
      <div class="header-left-skeleton">
        <van-skeleton :row="1" row-width="20px" animate />
      </div>
      <div class="header-center-skeleton">
        <van-skeleton :row="1" row-width="120px" animate />
      </div>
      <div class="header-right-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
    </div>

    <!-- Message area skeleton -->
    <div class="message-area-skeleton">
      <!-- User message bubble (right-aligned) -->
      <div class="user-bubble-skeleton">
        <van-skeleton :row="2" row-width="200px 150px" animate />
      </div>

      <!-- AI response placeholder -->
      <div class="ai-bubble-skeleton">
        <div class="ai-avatar-skeleton">
          <van-skeleton :row="1" row-width="32px" animate />
        </div>
        <div class="ai-content-skeleton">
          <!-- Thinking steps skeleton -->
          <div class="thinking-step-skeleton">
            <van-skeleton :row="1" row-width="140px" animate />
          </div>
          <div class="thinking-step-skeleton">
            <van-skeleton :row="1" row-width="180px" animate />
          </div>
          <!-- Response text skeleton -->
          <div class="response-text-skeleton">
            <van-skeleton :row="3" row-width="100% 90% 60%" animate />
          </div>
        </div>
      </div>
    </div>

    <!-- Input box skeleton (fixed at bottom) -->
    <div class="input-box-skeleton">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>
  </div>
</template>

<style scoped>
.ai-chat-skeleton {
  display: flex;
  flex-direction: column;
  position: fixed;
  inset: 0;
  bottom: calc(50px + env(safe-area-inset-bottom));
  background: var(--van-background, #f7f8fa);
  z-index: 10;
}

:global([data-theme='dark']) .ai-chat-skeleton {
  background: var(--bg-primary);
}

/* Header skeleton */
.chat-header-skeleton {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-primary, #fff);
  border-bottom: 1px solid var(--van-border-color, rgba(0, 0, 0, 0.08));
  min-height: 44px;
}

:global([data-theme='dark']) .chat-header-skeleton {
  border-bottom-color: rgba(255, 255, 255, 0.1);
}

.header-left-skeleton,
.header-right-skeleton {
  flex-shrink: 0;
}

.header-left-skeleton :deep(.van-skeleton),
.header-right-skeleton :deep(.van-skeleton),
.header-center-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.header-left-skeleton :deep(.van-skeleton__row),
.header-right-skeleton :deep(.van-skeleton__row),
.header-center-skeleton :deep(.van-skeleton__row) {
  height: 18px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

:global([data-theme='dark']) .header-left-skeleton :deep(.van-skeleton__row),
:global([data-theme='dark']) .header-right-skeleton :deep(.van-skeleton__row),
:global([data-theme='dark']) .header-center-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
}

/* Message area skeleton */
.message-area-skeleton {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* User bubble skeleton (right-aligned) */
.user-bubble-skeleton {
  align-self: flex-end;
  max-width: 80%;
  background: var(--van-primary-color, #6366f1);
  border-radius: 16px 16px 4px 16px;
  padding: 12px 16px;
}

.user-bubble-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.user-bubble-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.2);
  margin-top: 4px;
}

.user-bubble-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

/* AI bubble skeleton */
.ai-bubble-skeleton {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  max-width: 90%;
}

.ai-avatar-skeleton {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  overflow: hidden;
}

.ai-avatar-skeleton :deep(.van-skeleton) {
  padding: 0;
  height: 32px;
}

.ai-avatar-skeleton :deep(.van-skeleton__row) {
  height: 32px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.15);
}

.ai-content-skeleton {
  flex: 1;
  background: var(--card-bg, #fff);
  border-radius: 12px;
  padding: 12px 16px;
  border: 1px solid var(--van-border-color, rgba(0, 0, 0, 0.08));
}

:global([data-theme='dark']) .ai-content-skeleton {
  border-color: rgba(255, 255, 255, 0.1);
}

/* Thinking steps skeleton */
.thinking-step-skeleton {
  margin-bottom: 8px;
}

.thinking-step-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.thinking-step-skeleton :deep(.van-skeleton__row) {
  height: 12px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.12);
}

:global([data-theme='dark']) .thinking-step-skeleton :deep(.van-skeleton__row) {
  background: rgba(189, 187, 255, 0.15);
}

/* Response text skeleton */
.response-text-skeleton {
  margin-top: 12px;
}

.response-text-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.response-text-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
  margin-top: 6px;
}

:global([data-theme='dark']) .response-text-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

/* Input box skeleton (fixed at bottom) */
.input-box-skeleton {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  z-index: 100;
  padding: 8px 16px;
  background: transparent;
}

.input-box-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.input-box-skeleton :deep(.van-skeleton__row) {
  height: 80px;
  border-radius: 16px;
  background: rgba(0, 0, 0, 0.06);
}

:global([data-theme='dark']) .input-box-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}
</style>