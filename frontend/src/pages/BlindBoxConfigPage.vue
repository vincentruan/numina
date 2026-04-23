<template>
  <div class="blind-box-config-page">
    <van-nav-bar title="盲盒配置" left-arrow @click-left="$router.back()" />

    <van-loading v-if="loading" vertical class="page-loading">加载中...</van-loading>

    <template v-else-if="config">
      <van-cell-group inset title="基本设置">
        <van-cell title="启用盲盒功能" center>
          <template #right-icon>
            <van-switch v-model="form.enabled" @change="onSave" />
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group inset title="抽奖概率">
        <van-cell :title="`普通日触发概率: ${Math.round((form.base_draw_prob ?? 0) * 100)}%`">
          <template #label>
            <van-slider
              v-model="form.base_draw_prob"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="`普通日触发概率 ${Math.round((form.base_draw_prob ?? 0) * 100)}%`"
              @change="onSave"
            />
          </template>
        </van-cell>
        <van-cell :title="`特殊日触发概率: ${Math.round((form.special_day_prob ?? 0) * 100)}%`">
          <template #label>
            <van-slider
              v-model="form.special_day_prob"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="`特殊日触发概率 ${Math.round((form.special_day_prob ?? 0) * 100)}%`"
              @change="onSave"
            />
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group inset title="惊喜升级概率">
        <van-cell :title="`普通日惊喜概率: ${Math.round((form.surprise_prob_normal ?? 0) * 100)}%`">
          <template #label>
            <van-slider
              v-model="form.surprise_prob_normal"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="`普通日惊喜概率 ${Math.round((form.surprise_prob_normal ?? 0) * 100)}%`"
              @change="onSave"
            />
          </template>
        </van-cell>
        <van-cell :title="`父母生日惊喜概率: ${Math.round((form.surprise_prob_parent_bday ?? 0) * 100)}%`">
          <template #label>
            <van-slider
              v-model="form.surprise_prob_parent_bday"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="`父母生日惊喜概率 ${Math.round((form.surprise_prob_parent_bday ?? 0) * 100)}%`"
              @change="onSave"
            />
          </template>
        </van-cell>
        <van-cell :title="`兄弟姐妹生日惊喜概率: ${Math.round((form.surprise_prob_sibling_bday ?? 0) * 100)}%`">
          <template #label>
            <van-slider
              v-model="form.surprise_prob_sibling_bday"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="`兄弟姐妹生日惊喜概率 ${Math.round((form.surprise_prob_sibling_bday ?? 0) * 100)}%`"
              @change="onSave"
            />
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group inset title="权重参数">
        <van-field
          v-model.number="form.weight_scale"
          label="权重系数"
          type="number"
          placeholder="默认 2.0"
          @blur="onSave"
        />
        <van-field
          v-model.number="form.surprise_threshold_coins"
          label="惊喜门槛金币"
          type="number"
          placeholder="默认 200"
          @blur="onSave"
        />
      </van-cell-group>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, watch } from 'vue'
import { showToast } from 'vant'
import { useBlindBoxStore } from '@/stores/blindBox'
import { storeToRefs } from 'pinia'

const store = useBlindBoxStore()
const { config, loading } = storeToRefs(store)

const form = reactive({
  enabled: true,
  base_draw_prob: 0.3,
  special_day_prob: 0.8,
  weight_scale: 2.0,
  surprise_threshold_coins: 200,
  surprise_prob_normal: 0.05,
  surprise_prob_parent_bday: 0.6,
  surprise_prob_sibling_bday: 0.5,
})

onMounted(async () => {
  await store.fetchConfig()
  if (config.value) Object.assign(form, config.value)
})

watch(config, (val) => {
  if (val) Object.assign(form, val)
})

async function onSave() {
  await store.updateConfig({ ...form })
  showToast('✅ 已保存')
}
</script>

<style scoped>
.blind-box-config-page {
  min-height: 100vh;
  background: var(--van-background);
}
.page-loading {
  padding: 40px;
  display: flex;
  justify-content: center;
}
</style>
