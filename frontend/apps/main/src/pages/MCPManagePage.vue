<template>
  <div class="mcp-manage-page">
    <PageHeader :title="t('mcp.title')" />

    <van-cell-group inset :title="t('mcp.servers')" class="section">
      <van-cell
        v-for="server in servers"
        :key="server.id"
        :label="server.url"
        center
      >
        <template #title>
          <span>{{ server.name }}</span>
          <van-tag
            v-if="server.mcp_type === 'websearch'"
            type="primary"
            size="medium"
            style="margin-left: 6px"
          >
            {{ t('webSearch.title') }}
          </van-tag>
        </template>
        <template #value>
          <div class="cell-actions">
            <van-switch
              :model-value="server.is_enabled"
              size="20px"
              :disabled="!isOwner"
              @change="(v: boolean) => onToggle(server, v)"
            />
            <van-icon v-if="isOwner" name="edit" class="action-icon" @click="onEdit(server)" />
            <van-icon v-if="isOwner" name="delete-o" class="action-icon danger" @click="onDelete(server)" />
          </div>
        </template>
      </van-cell>

      <van-cell v-if="servers.length === 0" :title="t('mcp.empty')" />
    </van-cell-group>

    <div v-if="isOwner" class="add-btn-wrap">
      <van-button round block type="primary" icon="plus" @click="onAdd">
        {{ t('mcp.addServer') }}
      </van-button>
    </div>

    <!-- Add / Edit dialog -->
    <van-dialog
      v-model:show="showDialog"
      :title="editingServer ? t('mcp.editServer') : t('mcp.addServer')"
      show-cancel-button
      :before-close="onDialogClose"
    >
      <div class="dialog-form">
        <van-field v-model="form.name" :label="t('mcp.name')" :placeholder="t('mcp.namePlaceholder')" required />
        <van-field v-model="form.url" :label="t('mcp.url')" :placeholder="t('mcp.urlPlaceholder')" required />
        <van-field
          v-model="form.transport"
          :label="t('mcp.transport')"
          is-link
          readonly
          :placeholder="t('mcp.transportPlaceholder')"
          @click="showTransportPicker = true"
        />
        <van-field
          v-model="form.envVarsText"
          :label="t('mcp.envVars')"
          type="textarea"
          rows="3"
          :placeholder="t('mcp.envVarsPlaceholder')"
          :autosize="{ minHeight: 60 }"
        />
      </div>
    </van-dialog>

    <van-popup v-model:show="showTransportPicker" position="bottom" round>
      <van-picker
        :columns="transportOptions"
        @confirm="onTransportConfirm"
        @cancel="showTransportPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import {
  getMCPServers,
  createMCPServer,
  updateMCPServer,
  deleteMCPServer,
  type MCPServer,
} from '@/api/ai'

const { t } = useI18n()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const servers = ref<MCPServer[]>([])
const showDialog = ref(false)
const showTransportPicker = ref(false)
const editingServer = ref<MCPServer | null>(null)

const form = ref({
  name: '',
  url: '',
  transport: 'sse' as 'sse' | 'stdio',
  envVarsText: '',
})

const transportOptions = [
  { text: 'SSE', value: 'sse' },
  { text: 'stdio', value: 'stdio' },
]

async function load() {
  const res = await getMCPServers()
  servers.value = res.data
}

onMounted(load)

function onAdd() {
  editingServer.value = null
  form.value = { name: '', url: '', transport: 'sse', envVarsText: '' }
  showDialog.value = true
}

function onEdit(server: MCPServer) {
  editingServer.value = server
  form.value = {
    name: server.name,
    url: server.url,
    transport: server.transport,
    envVarsText: server.env_vars && Object.keys(server.env_vars).length > 0
        ? JSON.stringify(server.env_vars, null, 2)
        : '',
  }
  showDialog.value = true
}

async function onDelete(server: MCPServer) {
  await showConfirmDialog({ title: t('common.confirm'), message: t('mcp.deleteConfirm', { name: server.name }) })
  await deleteMCPServer(server.id)
  showSuccessToast(t('toast.deleted'))
  await load()
}

async function onToggle(server: MCPServer, enabled: boolean) {
  await updateMCPServer(server.id, { is_enabled: enabled })
  server.is_enabled = enabled
  showSuccessToast(enabled ? t('toast.enabled') : t('toast.disabled'))
}

function onTransportConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.transport = selectedValues[0] as 'sse' | 'stdio'
  showTransportPicker.value = false
}

async function onDialogClose(action: string) {
  if (action !== 'confirm') return true
  if (!form.value.name || !form.value.url) {
    showToast(t('mcp.nameUrlRequired'))
    return false
  }
  let envVars: Record<string, string> | null = null
  if (form.value.envVarsText.trim()) {
    try {
      envVars = JSON.parse(form.value.envVarsText)
    } catch {
      showToast(t('mcp.envVarsInvalidJson'))
      return false
    }
  }
  const payload = {
    name: form.value.name,
    url: form.value.url,
    transport: form.value.transport,
    env_vars: envVars,
  }
  if (editingServer.value) {
    await updateMCPServer(editingServer.value.id, payload)
  } else {
    await createMCPServer(payload)
  }
  showSuccessToast(t('toast.saved'))
  await load()
  return true
}
</script>

<style scoped>
.mcp-manage-page {
  min-height: 100vh;
  background: var(--van-background);
}
.section {
  margin-top: 12px;
}
.cell-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
.action-icon {
  font-size: 18px;
  cursor: pointer;
  color: var(--van-text-color-2);
}
.action-icon.danger {
  color: var(--van-danger-color);
}
.add-btn-wrap {
  padding: 16px;
}
.dialog-form {
  padding: 8px 0;
}
</style>
