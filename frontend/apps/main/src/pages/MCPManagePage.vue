<template>
  <div class="mcp-manage-page">
    <PageHeader :title="t('mcp.title')" />

    <van-cell-group inset :title="t('mcp.servers')" class="section">
      <van-cell
        v-for="server in servers"
        :key="server.id"
        :title="server.name"
        :label="server.url"
        center
        :is-link="isOwner"
        @click="isOwner && onEdit(server)"
      >
        <template #value>
          <div class="cell-actions" @click.stop>
            <van-switch
              :model-value="server.is_enabled"
              size="20px"
              :disabled="!isOwner"
              @change="(v: boolean) => onToggle(server, v)"
            />
            <van-icon v-if="isOwner" name="delete-o" class="action-icon danger" @click="onDelete(server)" />
          </div>
        </template>
      </van-cell>

      <van-cell v-if="servers.length === 0" :title="t('mcp.empty')" />
    </van-cell-group>

    <div v-if="isOwner" class="bottom-bar">
      <van-button round block type="primary" icon="plus" @click="onAdd">
        {{ t('mcp.addServer') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  getMCPServers,
  updateMCPServer,
  deleteMCPServer,
  type MCPServer,
} from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const servers = ref<MCPServer[]>([])

async function load() {
  const res = await getMCPServers()
  servers.value = res.data
}

onMounted(load)

function onAdd() {
  router.push({ name: 'MCPCreate' })
}

function onEdit(server: MCPServer) {
  router.push({ name: 'MCPEdit', params: { id: server.id } })
}

async function onDelete(server: MCPServer) {
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('mcp.deleteConfirm', { name: server.name }),
    })
    await deleteMCPServer(server.id)
    showToast(t('toast.deleted'))
    await load()
  } catch {
    // cancelled
  }
}

async function onToggle(server: MCPServer, enabled: boolean) {
  await updateMCPServer(server.id, { is_enabled: enabled })
  server.is_enabled = enabled
  showToast(enabled ? t('toast.enabled') : t('toast.disabled'))
}
</script>

<style scoped>
.mcp-manage-page {
  min-height: 100vh;
  background: var(--van-background);
  padding-bottom: calc(120px + env(safe-area-inset-bottom));
}
.section {
  margin-top: 12px;
}
.cell-actions {
  display: flex;
  align-items: center;
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
.bottom-bar {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: var(--van-background);
}
</style>
