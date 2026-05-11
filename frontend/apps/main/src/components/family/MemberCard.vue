<template>
  <van-cell class="member-card" :title="member.display_name" :label="member.username ? '@' + member.username : (member.role === 'child' ? t('memberCard.childAccount') : '')">
    <template #icon>
      <div class="avatar" :style="{ background: member.avatar_color || 'var(--color-primary)' }">
        {{ member.display_name.charAt(0) }}
      </div>
    </template>
    <template #value>
      <van-tag :type="member.role === 'owner' ? 'primary' : 'default'" size="medium">
        {{ member.role === 'owner' ? t('memberCard.owner') : t('memberCard.member') }}
      </van-tag>
    </template>
  </van-cell>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { User } from '@/types'

const { t } = useI18n()

defineProps<{
  member: User
}>()
</script>

<style scoped>
.member-card {
  margin-bottom: 8px;
  border-radius: 8px;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  margin-right: 10px;
}
</style>
