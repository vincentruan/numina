<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import {
  getMCPServers,
  createMCPServer,
  updateMCPServer,
  type MCPServer,
} from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

const serverId = computed(() => {
  const v = route.params.id
  return Array.isArray(v) ? v[0] : v
})
const isEdit = computed(() => !!serverId.value)

const saving = ref(false)
const showTransportPicker = ref(false)
const showMcpTypePicker = ref(false)
const loaded = ref(!isEdit.value)

const form = reactive({
  name: '',
  url: '',
  transport: 'sse' as 'sse' | 'stdio',
  mcp_type: 'general' as 'general' | 'websearch',
  envVarsText: '',
})

const transportOptions = [
  { text: 'SSE', value: 'sse' },
  { text: 'stdio', value: 'stdio' },
]

const mcpTypeOptions = [
  { text: t('mcp.typeGeneral'), value: 'general' },
  { text: t('mcp.typeWebsearch'), value: 'websearch' },
]

function transportLabel(transport: 'sse' | 'stdio'): string {
  return transport === 'sse' ? 'SSE' : 'stdio'
}

function mcpTypeLabel(mcpType: 'general' | 'websearch'): string {
  return mcpType === 'general' ? t('mcp.typeGeneral') : t('mcp.typeWebsearch')
}

function loadServer(server: MCPServer) {
  form.name = server.name
  form.url = server.url
  form.transport = server.transport
  form.mcp_type = server.mcp_type || 'general'
  form.envVarsText =
    server.env_vars && Object.keys(server.env_vars).length > 0
      ? JSON.stringify(server.env_vars, null, 2)
      : ''
}

function onTransportConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.transport = selectedValues[0] as 'sse' | 'stdio'
  showTransportPicker.value = false
}

function onMcpTypeConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.mcp_type = selectedValues[0] as 'general' | 'websearch'
  showMcpTypePicker.value = false
}

async function onSave() {
  if (!form.name.trim() || !form.url.trim()) {
    showToast(t('mcp.nameUrlRequired'))
    return
  }
  let envVars: Record<string, string> | null = null
  if (form.envVarsText.trim()) {
    try {
      envVars = JSON.parse(form.envVarsText)
    } catch {
      showToast(t('mcp.envVarsInvalidJson'))
      return
    }
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      url: form.url.trim(),
      transport: form.transport,
      mcp_type: form.mcp_type,
      env_vars: envVars,
    }
    if (isEdit.value && serverId.value) {
      await updateMCPServer(serverId.value, payload)
    } else {
      await createMCPServer(payload)
    }
    showSuccessToast(t('toast.saved'))
    router.back()
  } catch {
    showFailToast(t('toast.saveFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (isEdit.value && serverId.value) {
    try {
      const res = await getMCPServers()
      const server = res.data.find((s) => s.id === serverId.value)
      if (server) {
        loadServer(server)
      } else {
        showFailToast(t('toast.loadFailed'))
        router.replace({ name: 'MCPManage' })
        return
      }
    } catch {
      showFailToast(t('toast.loadFailed'))
      router.replace({ name: 'MCPManage' })
      return
    } finally {
      loaded.value = true
    }
  }
})
</script>

<template>
  <div class="mcp-form-page">
    <PageHeader :title="isEdit ? t('mcp.editServer') : t('mcp.addServer')" />

    <van-cell-group v-if="loaded" inset class="section">
      <van-field
        v-model="form.name"
        :label="t('mcp.name')"
        :placeholder="t('mcp.namePlaceholder')"
        required
      />
      <van-field
        v-model="form.url"
        :label="t('mcp.url')"
        :placeholder="t('mcp.urlPlaceholder')"
        required
      />
      <van-cell
        :title="t('mcp.transport')"
        :value="transportLabel(form.transport)"
        is-link
        @click="showTransportPicker = true"
      />
      <van-cell
        :title="t('mcp.type')"
        :value="mcpTypeLabel(form.mcp_type)"
        is-link
        @click="showMcpTypePicker = true"
      />
      <van-field
        v-model="form.envVarsText"
        :label="t('mcp.envVars')"
        type="textarea"
        rows="4"
        :placeholder="t('mcp.envVarsPlaceholder')"
        :autosize="{ minHeight: 80 }"
      />
    </van-cell-group>

    <div v-if="loaded" class="bottom-bar">
      <van-button
        type="primary"
        block
        round
        :loading="saving"
        @click="onSave"
      >
        {{ isEdit ? t('mcp.updateBtn') : t('mcp.createBtn') }}
      </van-button>
    </div>

    <van-popup v-model:show="showTransportPicker" position="bottom" round>
      <van-picker
        :columns="transportOptions"
        :model-value="[form.transport]"
        @confirm="onTransportConfirm"
        @cancel="showTransportPicker = false"
      />
    </van-popup>

    <van-popup v-model:show="showMcpTypePicker" position="bottom" round>
      <van-picker
        :columns="mcpTypeOptions"
        :model-value="[form.mcp_type]"
        @confirm="onMcpTypeConfirm"
        @cancel="showMcpTypePicker = false"
      />
    </van-popup>
  </div>
</template>

<style scoped>
.mcp-form-page {
  background: var(--van-background);
  min-height: 100vh;
  padding-bottom: calc(120px + env(safe-area-inset-bottom));
}

.section {
  margin-top: 12px;
}

.bottom-bar {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: var(--van-background);
}
</style>
