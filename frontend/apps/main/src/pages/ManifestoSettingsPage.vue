<template>
  <div class="manifesto-settings-page">
    <van-nav-bar
      :title="t('manifesto.settingsGroup')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-cell-group inset class="section">
      <van-cell
        :title="t('manifesto.editManifesto')"
        is-link
        icon="certificate"
        @click="goManifestoEdit"
      />
      <van-cell
        :title="t('manifesto.versionHistory')"
        is-link
        icon="orders-o"
        @click="showHistory = true"
      />
      <van-cell
        :title="t('manifesto.feedbackList')"
        is-link
        icon="comment-o"
        @click="showFeedback = true"
      >
        <template #right-icon>
          <van-badge v-if="unreadFeedbackCount > 0" :content="unreadFeedbackCount" />
        </template>
      </van-cell>
    </van-cell-group>

    <ManifestoHistoryDialog v-model:visible="showHistory" />
    <ManifestoFeedbackList v-model:visible="showFeedback" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import * as manifestoApi from '@/api/manifesto'
import ManifestoHistoryDialog from '@/components/manifesto/ManifestoHistoryDialog.vue'
import ManifestoFeedbackList from '@/components/manifesto/ManifestoFeedbackList.vue'

defineOptions({ name: 'ManifestoSettings' })

const { t } = useI18n()
const router = useRouter()
const showHistory = ref(false)
const showFeedback = ref(false)
const unreadFeedbackCount = ref(0)

function goManifestoEdit() {
  manifestoApi.getCurrentManifesto()
    .then((res) => {
      if (res.data && res.data.id) {
        router.push('/manifesto/edit')
      } else {
        router.push('/manifesto/template-select')
      }
    })
    .catch(() => {
      showToast(t('manifesto.notFound'))
      router.push('/manifesto/template-select')
    })
}

async function loadUnreadCount() {
  try {
    const res = await manifestoApi.getFeedbackList()
    unreadFeedbackCount.value = (res.data ?? []).filter(f => !f.is_read).length
  } catch {
    unreadFeedbackCount.value = 0
  }
}

onMounted(() => {
  loadUnreadCount()
})
</script>

<style scoped>
.manifesto-settings-page {
  padding-bottom: 32px;
}
.section {
  margin-top: 12px;
}
</style>
