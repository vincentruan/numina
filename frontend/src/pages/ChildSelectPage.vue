<template>
  <div class="child-select-page">
    <div class="page-header">
      <h1 class="page-title">选择孩子</h1>
    </div>

    <div v-if="loading" class="loading-state">
      <van-loading size="32px" />
    </div>

    <div v-else-if="children.length === 0" class="empty-state">
      <p>暂无孩子账号</p>
    </div>

    <div v-else class="children-list">
      <div
        v-for="child in children"
        :key="child.id"
        class="child-card"
        @click="selectChild(child)"
      >
        <div class="child-avatar" :style="{ backgroundColor: child.avatar_color }">
          {{ child.display_name.charAt(0) }}
        </div>
        <div class="child-info">
          <span class="child-name">{{ child.display_name }}</span>
          <span class="child-username">@{{ child.username }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { ChildUser } from '@/types'
import { listChildren, getFamilyChildren } from '@/api/children'
import { getChildFamilyId } from '@/utils/storage'

const router = useRouter()
const children = ref<ChildUser[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const familyId = getChildFamilyId()
    if (familyId) {
      children.value = await getFamilyChildren(familyId)
    } else {
      children.value = await listChildren()
    }
  } catch {
    // leave empty
  } finally {
    loading.value = false
  }
})

function selectChild(child: ChildUser) {
  router.push({
    name: 'ChildAuth',
    query: {
      childId: child.id,
      username: child.username,  // 新增：传递 username
      displayName: child.display_name,
      avatarColor: child.avatar_color,
    },
  })
}
</script>

<style scoped>
.child-select-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
  padding: 40px 16px 24px;
}

.page-header {
  text-align: center;
  margin-bottom: 32px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  margin: 0;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding-top: 60px;
}

.empty-state {
  text-align: center;
  color: #999;
  padding-top: 60px;
}

.children-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 400px;
  margin: 0 auto;
}

.child-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 16px;
  padding: 16px 20px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.child-card:active {
  transform: scale(0.97);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.child-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.child-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.child-name {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.child-username {
  font-size: 14px;
  color: #666;
}
</style>
