<template>
  <div class="child-bind-page">
    <div v-if="loading" class="loading-state">
      <van-loading size="32px" />
      <p>正在验证绑定链接…</p>
    </div>

    <div v-else-if="error" class="error-state">
      <van-icon name="warning-o" size="48px" color="#e74c3c" />
      <p class="error-text">{{ error }}</p>
      <van-button round type="primary" @click="router.push('/login')">返回登录</van-button>
    </div>

    <div v-else-if="bindInfo" class="bind-success">
      <van-icon name="checked" size="48px" color="#07c160" />
      <h2 class="family-name">{{ bindInfo.family_name }}</h2>
      <p class="subtitle">已绑定家庭，以下孩子账号可用：</p>
      <div class="children-list">
        <div v-for="child in bindInfo.children" :key="child.id" class="child-item">
          <div class="child-avatar" :style="{ backgroundColor: child.avatar_color }">
            {{ child.display_name.charAt(0) }}
          </div>
          <span>{{ child.display_name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ChildBindInfo } from '@/types'
import { getChildBindInfo } from '@/api/children'
import { setChildFamilyId } from '@numina/auth'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref<string | null>(null)
const bindInfo = ref<ChildBindInfo | null>(null)

onMounted(async () => {
  const token = route.query.token as string | undefined
  if (!token) {
    error.value = '绑定链接无效'
    loading.value = false
    return
  }
  try {
    const info = await getChildBindInfo(token)
    setChildFamilyId(info.family_id)
    bindInfo.value = info
    setTimeout(() => router.push('/child/select'), 1500)
  } catch {
    error.value = '绑定链接已过期或已使用，请重新获取'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.child-bind-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
  padding: 24px;
}

.loading-state,
.error-state,
.bind-success {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.error-text {
  color: #e74c3c;
  font-size: 16px;
  margin: 0;
}

.family-name {
  font-size: 22px;
  font-weight: 700;
  color: #333;
  margin: 0;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.children-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  max-width: 280px;
}

.child-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 12px;
  padding: 12px 16px;
}

.child-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
</style>
