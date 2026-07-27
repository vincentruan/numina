<template>
  <div class="asset-detail-page">
    <!-- Skeleton during initial load -->
    <ChildAssetDetailSkeleton v-if="loading" />

    <!-- Actual content -->
    <template v-else>
    <PageHeader :title="t('assetDetail.title')" />

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-if="!asset" class="empty-state">
      <p class="empty-icon">🎁</p>
      <p class="empty-text">{{ t('errors.LOAD_FAILED') }}</p>
      <button class="btn-back" @click="router.replace('/wishes')">{{ t('common.back') }}</button>
    </div>

    <div v-else class="asset-card">
      <van-image
        v-if="asset.image_url"
        :src="asset.image_url"
        width="100%"
        height="200px"
        fit="cover"
        radius="var(--radius-lg)"
        class="asset-image"
      />
      <div v-else class="asset-image-placeholder">🎁</div>

      <div class="asset-info">
        <p class="asset-name">{{ asset.name }}</p>

        <div v-if="asset.purchase_date" class="info-row">
          <span class="info-label">{{ t('assetDetail.purchaseDate') }}</span>
          <span class="info-value">{{ formatDate(asset.purchase_date) }}</span>
        </div>

        <div v-if="asset.purchase_price != null" class="info-row">
          <span class="info-label">{{ t('assetDetail.purchasePrice') }}</span>
          <span class="info-value">{{ asset.purchase_price.toLocaleString() }}</span>
        </div>

        <div v-if="asset.current_value != null" class="info-row">
          <span class="info-label">{{ t('assetDetail.currentValue') }}</span>
          <span class="info-value">{{ asset.current_value.toLocaleString() }}</span>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePageLoading } from '@/composables/usePageLoading'
import ChildAssetDetailSkeleton from '@/components/skeletons/ChildAssetDetailSkeleton.vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getChildAsset, type ChildAsset } from '@/api/treasures'
import { parseLocalDate } from '@/utils/format'
import PageHeader from '@/components/common/PageHeader.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const asset = ref<ChildAsset | null>(null)
const loading = ref(true)
const error = ref('')

function formatDate(dateStr: string): string {
  return parseLocalDate(dateStr).toLocaleDateString(locale.value, { year: 'numeric', month: 'short', day: 'numeric' })
}

async function load() {
  loading.value = true
  error.value = ''
  increment()
  try {
    asset.value = await getChildAsset(String(route.params.id))
  } catch {
    error.value = t('errors.LOAD_FAILED')
  } finally {
    loading.value = false
    decrement()
  }
}

onMounted(load)
</script>

<style scoped>
.asset-detail-page {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: var(--space-md);
}

.loading {
  text-align: center;
  padding: 40px 0;
  color: var(--color-muted-soft);
  font-family: Inter, sans-serif;
  font-size: 15px;
}

.error-msg {
  background: var(--color-brand-coral);
  color: var(--color-on-primary);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  text-align: center;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon { font-size: 56px; margin: 0 0 12px; }
.empty-text {
  font-family: Inter, sans-serif;
  font-size: 16px;
  color: var(--color-muted-soft);
  margin: 0 0 20px;
}
.btn-back {
  background: var(--color-brand-peach);
  color: var(--color-ink);
  border: none;
  border-radius: var(--radius-md);
  padding: 10px 28px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.asset-card {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-hairline);
  overflow: hidden;
  margin-top: var(--space-md);
}

.asset-image {
  display: block;
}

.asset-image-placeholder {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 64px;
  background: var(--color-surface-card);
}

.asset-info {
  padding: var(--space-lg);
}

.asset-name {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-hairline);
}
.info-row:last-child { border-bottom: none; }

.info-label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
}

.info-value {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}
</style>
