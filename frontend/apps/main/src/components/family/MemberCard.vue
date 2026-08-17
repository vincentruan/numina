<template>
  <van-cell class="member-card" :title="member.display_name" :label="member.username ? '@' + member.username : (member.role === 'child' ? t('memberCard.childAccount') : '')">
    <template #icon>
      <UserAvatar
        :avatar-url="member.avatar_url ?? null"
        :avatar-color="member.avatar_color || '#4F46E5'"
        :display-name="member.display_name"
        :size="36"
      />
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
import UserAvatar from '@/components/common/UserAvatar.vue'

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
