<template>
  <div class="ai-allocation-page">
    <PageHeader title="配置漂移检测" />

    <!-- Target setup -->
    <van-cell-group inset title="目标配置">
      <van-cell
        v-if="!editingTarget"
        title="当前目标"
        :value="hasTarget ? '已设置' : '未设置'"
        is-link
        @click="startEdit"
      />
      <template v-if="editingTarget">
        <div class="target-editor">
          <div v-for="(pct, cat) in editTargets" :key="cat" class="target-row">
            <span class="target-cat">{{ cat }}</span>
            <van-stepper
              v-model="editTargets[cat]"
              :min="0"
              :max="100"
              :step="5"
              integer
            />
            <span class="target-pct">{{ editTargets[cat] }}%</span>
          </div>
          <div class="target-total" :class="{ error: targetTotal !== 100 }">
            <van-icon v-if="targetTotal !== 100" name="warning-o" aria-hidden="true" />
            合计：{{ targetTotal }}%（需等于100%）
          </div>
          <div class="target-actions">
            <van-button size="small" plain @click="editingTarget = false">取消</van-button>
            <van-button size="small" type="primary" :disabled="targetTotal !== 100" @click="onSaveTarget">保存</van-button>
          </div>
        </div>
      </template>
    </van-cell-group>

    <!-- Drift check -->
    <div v-if="hasTarget" class="check-section">
      <van-button block type="primary" :loading="checking" @click="onCheck">检测配置漂移</van-button>
    </div>

    <!-- Results -->
    <template v-if="driftResult">
      <div v-if="!driftResult.has_significant_drift" class="no-drift">
        <van-empty image="success" description="配置在目标范围内，无需再平衡" />
      </div>
      <template v-else>
        <div v-if="driftResult.narrative" class="narrative-card">
          <div class="narrative-label">AI 建议</div>
          <p class="narrative-text">{{ driftResult.narrative }}</p>
        </div>

        <van-cell-group inset title="各类别漂移">
          <div v-for="d in driftResult.drifts" :key="d.category" class="drift-row">
            <div class="drift-info">
              <span class="drift-cat">{{ d.category }}</span>
              <span class="drift-nums">
                目标 {{ d.target_pct }}% → 当前 {{ d.current_pct }}%
              </span>
            </div>
            <span
              class="drift-badge"
              :class="d.exceeds_threshold ? 'badge-warn' : 'badge-ok'"
            >
              {{ d.drift > 0 ? '+' : '' }}{{ d.drift }}%
            </span>
          </div>
        </van-cell-group>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getAllocationTarget, setAllocationTarget, checkAllocationDrift } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const hasTarget = ref(false)
const editingTarget = ref(false)
const checking = ref(false)
const driftResult = ref<any>(null)

// Default categories to configure
const DEFAULT_CATEGORIES = ['实物资产', '金融资产', '其他']
const editTargets = reactive<Record<string, number>>({})

const targetTotal = computed(() => Object.values(editTargets).reduce((a, b) => a + b, 0))

function startEdit() {
  editingTarget.value = true
}

async function onSaveTarget() {
  try {
    await setAllocationTarget({
      category_targets: { ...editTargets },
      drift_threshold: 10,
    })
    hasTarget.value = true
    editingTarget.value = false
    showToast(t('toast.aiTargetSaved'))
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败')
  }
}

async function onCheck() {
  checking.value = true
  try {
    const res = await checkAllocationDrift()
    driftResult.value = res.data
  } catch {
    showToast(t('toast.aiDetectFailed'))
  } finally {
    checking.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getAllocationTarget()
    if (res.data.has_target) {
      hasTarget.value = true
      const targets = res.data.category_targets as Record<string, number>
      Object.assign(editTargets, targets)
    } else {
      DEFAULT_CATEGORIES.forEach(c => { editTargets[c] = 0 })
    }
  } catch {
    DEFAULT_CATEGORIES.forEach(c => { editTargets[c] = 0 })
  }
})
</script>

<style scoped>
.ai-allocation-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
.target-editor { padding: 12px 16px; }
.target-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}
.target-cat { flex: 1; font-size: 14px; color: var(--text-primary); }
.target-pct { width: 36px; text-align: right; font-size: 13px; color: var(--text-secondary); }
.target-total {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 0;
  text-align: right;
}
.target-total.error { color: #f44336; }
.target-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
}
.check-section { padding: 12px 16px; }
.no-drift { padding: 40px 16px; }
.narrative-card {
  background: var(--bg-primary);
  margin: 12px 16px;
  border-radius: 12px;
  padding: 14px 16px;
}
.narrative-label {
  font-size: 12px;
  color: var(--van-primary-color);
  font-weight: 600;
  margin-bottom: 6px;
}
.narrative-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}
.drift-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-color, #f5f5f5);
}
.drift-info { display: flex; flex-direction: column; gap: 2px; }
.drift-cat { font-size: 14px; color: var(--text-primary); }
.drift-nums { font-size: 12px; color: var(--text-secondary); }
.drift-badge {
  font-size: 13px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 10px;
}
.badge-warn { background: #fce4ec; color: #c62828; }
.badge-ok { background: #e8f5e9; color: #2e7d32; }
</style>
