<template>
  <van-cell-group v-if="visible" inset class="chart-section manifesto-card">
    <van-collapse v-model="expanded" @change="onExpandChange">
      <van-collapse-item name="manifesto">
        <template #title>
          <div class="manifesto-header">
            <span class="manifesto-title">
              <van-icon name="certificate" class="manifesto-icon" />
              <span class="manifesto-title__text">{{ t('manifesto.title') }}</span>
            </span>
            <span class="manifesto-summary">
              {{ summary!.signed_count }}/{{ summary!.total_members }} {{ t('manifesto.signed') }}
            </span>
            <van-icon name="arrow" class="manifesto-arrow" />
          </div>
        </template>

        <van-loading v-if="detailLoading" size="24px" class="manifesto-loading" />
        <template v-else-if="manifesto">
          <van-cell
            v-for="sig in signerRows"
            :key="sig.userId"
            :title="sig.displayName"
            :value="sig.signed ? t('manifesto.signed') : t('manifesto.pending')"
            :label="sig.signedAt ? `${t('manifesto.signedAt')} ${sig.signedAt}` : undefined"
          >
            <template #right-icon>
              <van-icon v-if="sig.signed" name="success" color="var(--van-success-color, #07c160)" />
              <van-icon v-else name="clock-o" color="var(--van-text-color-3, #c8c9cc)" />
            </template>
          </van-cell>
          <div class="manifesto-actions">
            <van-button plain type="primary" size="small" @click="goDetail">
              {{ t('manifesto.viewDetail') }}
            </van-button>
          </div>
        </template>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import * as manifestoApi from '@/api/manifesto'
import type {
  ManifestoDashboardSummary,
  Manifesto,
  ManifestoSignature,
} from '@/types/manifesto'
import { useFamilyStore } from '@/stores/family'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()

const visible = ref(false)
const summary = ref<ManifestoDashboardSummary | null>(null)
const manifesto = ref<Manifesto | null>(null)
const detailLoading = ref(false)
const expanded = ref<string[]>([])

const signerRows = computed(() => {
  if (!manifesto.value) return []
  const signedUserIds = new Set(manifesto.value.signatures.map((s: ManifestoSignature) => s.user_id))
  return familyStore.members
    .filter(m => m.role !== 'child')
    .map(m => ({
      userId: m.id,
      displayName: m.display_name,
      signed: signedUserIds.has(m.id),
      signedAt: manifesto.value!.signatures.find((s: ManifestoSignature) => s.user_id === m.id)?.signed_at ?? null,
    }))
    .sort((a, b) => (a.signed === b.signed ? 0 : a.signed ? -1 : 1))
})

function goDetail() {
  router.push('/manifesto/preview')
}

async function loadDetail() {
  if (manifesto.value || !summary.value) return
  detailLoading.value = true
  try {
    if (familyStore.members.length === 0) {
      await familyStore.fetchFamily().catch(() => { /* non-critical */ })
    }
    const res = await manifestoApi.getCurrentManifesto()
    manifesto.value = res.data
  } catch {
    // Non-critical
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  try {
    const res = await manifestoApi.getDashboardSummary()
    if (res.data && res.data.manifesto_id) {
      summary.value = res.data
      visible.value = true
    }
  } catch {
    visible.value = false
  }
})

async function onExpandChange(names: string[]) {
  if (names.includes('manifesto')) {
    await loadDetail()
  }
}
</script>

<style scoped>
.manifesto-card {
  display: block;
  margin: 8px 0;
}
.manifesto-card :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}
.manifesto-card :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  min-width: 0;
}
.manifesto-card :deep(.van-cell__value) {
  flex: none;
  width: 0;
}
.manifesto-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
}
.manifesto-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.manifesto-icon {
  font-size: 18px;
  color: var(--van-primary-color);
  flex-shrink: 0;
}
.manifesto-title__text {
  color: var(--van-text-color);
  font-size: 14px;
  font-weight: 500;
}
.manifesto-summary {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.manifesto-arrow {
  color: var(--van-text-color-3);
  flex-shrink: 0;
}
.manifesto-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}
.manifesto-actions {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
}
</style>
