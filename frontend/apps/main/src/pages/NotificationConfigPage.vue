<template>
  <van-nav-bar
    :title="t('reminders.notificationSettings')"
    left-arrow
    @click-left="$router.back()"
  />

  <div class="page-content">
    <van-cell-group inset :title="t('reminders.channelGroupTitle')" class="section">
      <van-swipe-cell v-for="channel in channels" :key="channel.id">
        <van-cell
          :title="channel.name"
          :label="channelLabel(channel)"
          :value="channel.is_enabled ? t('reminders.channelEnabled') : t('reminders.channelDisabled')"
          is-link
          @click="editChannel(channel)"
        />
        <template #right>
          <van-button
            square
            type="danger"
            :text="t('common.delete')"
            class="delete-btn"
            @click="removeChannel(channel.id)"
          />
        </template>
      </van-swipe-cell>
      <van-cell :title="t('reminders.addChannel')" is-link icon="plus" @click="openAdd" />
    </van-cell-group>
  </div>

  <van-popup v-model:show="showSheet" position="bottom" round teleport="body" :style="{ height: '80%' }">
    <div class="popup-content">
      <van-nav-bar :title="editingChannel ? t('reminders.editChannelTitle') : t('reminders.addChannelTitle')">
        <template #right>
          <van-icon name="cross" @click="showSheet = false" />
        </template>
      </van-nav-bar>
      <van-cell-group inset>
        <van-field v-model="form.name" :label="t('reminders.channelNameLabel')" :placeholder="t('reminders.channelNamePlaceholder')" />
        <van-field
          v-if="!editingChannel"
          :model-value="t('reminders.channelType.' + form.channel_type)"
          :label="t('reminders.channelTypeLabel')"
          readonly
          is-link
          @click="showTypePicker = true"
        />
        <template v-if="form.channel_type === 'telegram'">
          <van-field v-model="form.bot_token" :label="t('reminders.botTokenLabel')" :placeholder="t('reminders.botTokenPlaceholder')" type="password" />
          <van-field v-model="form.chat_id" :label="t('reminders.chatIdLabel')" :placeholder="t('reminders.chatIdPlaceholder')" />
        </template>
        <template v-if="form.channel_type === 'feishu'">
          <van-field v-model="form.webhook_url" :label="t('reminders.webhookUrlLabel')" :placeholder="t('reminders.webhookUrlPlaceholder')" />
          <van-field v-model="form.secret" :label="t('reminders.feishuSecretLabel')" :placeholder="t('reminders.feishuSecretPlaceholder')" type="password" />
        </template>
        <template v-if="form.channel_type === 'email'">
          <van-field v-model="form.smtp_host" :label="t('reminders.smtpHostLabel')" :placeholder="t('reminders.smtpHostPlaceholder')" />
          <van-field v-model="form.smtp_port" :label="t('reminders.smtpPortLabel')" type="number" :placeholder="t('reminders.smtpPortPlaceholder')" />
          <van-field v-model="form.smtp_user" :label="t('reminders.smtpUserLabel')" />
          <van-field v-model="form.smtp_password" :label="t('reminders.smtpPasswordLabel')" type="password" />
          <van-field v-model="form.smtp_from" :label="t('reminders.smtpFromLabel')" :placeholder="t('reminders.smtpFromPlaceholder')" />
          <van-field v-model="form.email_to" :label="t('reminders.emailToLabel')" :placeholder="t('reminders.smtpToPlaceholder')" />
        </template>

        <!-- Subscription events — opens EventSelectorPopup -->
        <van-cell
          :title="t('reminders.subscriptions')"
          :value="subscriptionSummary"
          is-link
          @click="showEventSelector = true"
        />

        <!-- Digest mode toggle -->
        <van-cell :title="t('reminders.digestMode')" :value="t('reminders.digestModeDesc')">
          <template #right-icon>
            <van-switch v-model="form.digestEnabled" size="20px" />
          </template>
        </van-cell>
        <van-field
          v-if="form.digestEnabled"
          :model-value="form.digest_time"
          :label="t('reminders.digestTime')"
          readonly
          is-link
          @click="showTimePicker = true"
        />

        <!-- Mention config — Telegram / Feishu only -->
        <van-cell
          v-if="form.channel_type === 'telegram' || form.channel_type === 'feishu'"
          :title="t('reminders.mentionConfig')"
          :value="mentionSummary"
          is-link
          @click="showMentionSheet = true"
        />

        <van-cell>
          <van-button type="primary" block @click="saveChannel">{{ t('common.save') }}</van-button>
        </van-cell>
      </van-cell-group>
    </div>
  </van-popup>

  <!-- Event selector popup -->
  <EventSelectorPopup
    v-model="showEventSelector"
    :initial-types="form.subscriptions"
    @save="onEventsSaved"
  />

  <!-- Mention config popup -->
  <van-popup v-model:show="showMentionSheet" position="bottom" round teleport="body" :style="{ height: '50%' }">
    <div class="popup-content">
      <van-nav-bar :title="t('reminders.mentionConfigTitle')">
        <template #right>
          <van-icon name="cross" @click="showMentionSheet = false" />
        </template>
      </van-nav-bar>
      <van-cell-group inset>
        <template v-if="form.channel_type === 'telegram'">
          <van-field v-model="form.mention_username" :label="t('reminders.mentionUsername')" :placeholder="t('reminders.mentionUsernamePlaceholder')" />
          <van-field v-model="form.mention_user_id" :label="t('reminders.mentionUserId')" :placeholder="t('reminders.mentionUserIdPlaceholder')" />
        </template>
        <template v-if="form.channel_type === 'feishu'">
          <van-field v-model="form.mention_name" :label="t('reminders.mentionName')" :placeholder="t('reminders.mentionNamePlaceholder')" />
          <van-field v-model="form.mention_open_id" :label="t('reminders.mentionOpenId')" :placeholder="t('reminders.mentionOpenIdPlaceholder')" />
        </template>
        <van-cell>
          <van-button type="primary" block @click="showMentionSheet = false">{{ t('common.save') }}</van-button>
        </van-cell>
      </van-cell-group>
    </div>
  </van-popup>

  <!-- Time picker for digest time -->
  <van-popup v-model:show="showTimePicker" position="bottom" round teleport="body" :z-index="3000">
    <van-time-picker
      v-model="digestTimeValue"
      :title="t('reminders.digestTime')"
      :columns-type="['hour', 'minute']"
      @confirm="onTimeConfirm"
      @cancel="showTimePicker = false"
    />
  </van-popup>

  <van-popup v-model:show="showTypePicker" position="bottom" round :teleport="'body'" :z-index="3000">
    <van-picker
      :columns="typePickerColumns"
      @confirm="onTypeConfirm"
      @cancel="showTypePicker = false"
    />
  </van-popup>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showSuccessToast } from 'vant'
import {
  notificationChannelsApi,
  type NotificationChannelResponse,
} from '@/api/notificationChannels'

const { t } = useI18n()

const channels = ref<NotificationChannelResponse[]>([])
const showSheet = ref(false)
const showTypePicker = ref(false)
const showEventSelector = ref(false)
const showMentionSheet = ref(false)
const showTimePicker = ref(false)
const editingChannel = ref<NotificationChannelResponse | null>(null)

const typePickerColumns = computed(() => [
  { text: t('reminders.channelType.telegram'), value: 'telegram' },
  { text: t('reminders.channelType.email'), value: 'email' },
  { text: t('reminders.channelType.feishu'), value: 'feishu' },
])

const form = reactive({
  name: '',
  channel_type: 'telegram' as 'telegram' | 'email' | 'feishu',
  bot_token: '',
  chat_id: '',
  webhook_url: '',
  secret: '',
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  smtp_from: '',
  email_to: '',
  subscriptions: [] as string[],
  digestEnabled: false,
  digest_time: '21:00',
  // Telegram mention
  mention_username: '',
  mention_user_id: '',
  // Feishu mention
  mention_name: '',
  mention_open_id: '',
})

/** Digest time as [hour, minute] array for van-time-picker */
const digestTimeValue = computed({
  get: () => {
    const [h, m] = form.digest_time.split(':')
    return [h || '21', m || '00']
  },
  set: (val: string[]) => {
    form.digest_time = `${val[0]}:${val[1]}`
  },
})

const subscriptionSummary = computed(() => {
  const count = form.subscriptions.length
  if (count === 0) return t('reminders.noSubscriptions')
  if (count <= 3) {
    return form.subscriptions.map((s) => t('reminders.types.' + s)).join('、')
  }
  return t('reminders.subscriptionCount', { count })
})

const mentionSummary = computed(() => {
  if (form.channel_type === 'telegram') {
    return form.mention_username || t('reminders.notConfigured')
  }
  if (form.channel_type === 'feishu') {
    return form.mention_name || t('reminders.notConfigured')
  }
  return ''
})

function resetForm() {
  form.name = ''
  form.channel_type = 'telegram'
  form.bot_token = ''
  form.chat_id = ''
  form.webhook_url = ''
  form.secret = ''
  form.smtp_host = ''
  form.smtp_port = 587
  form.smtp_user = ''
  form.smtp_password = ''
  form.smtp_from = ''
  form.email_to = ''
  form.subscriptions = []
  form.digestEnabled = false
  form.digest_time = '21:00'
  form.mention_username = ''
  form.mention_user_id = ''
  form.mention_name = ''
  form.mention_open_id = ''
}

function channelLabel(channel: NotificationChannelResponse): string {
  const typeName = t('reminders.channelType.' + channel.channel_type)
  const subCount = channel.subscriptions.length
  const subLabel = subCount > 0
    ? t('reminders.subscriptionCount', { count: subCount })
    : t('reminders.noSubscriptions')
  const digestLabel = channel.digest_mode === 'daily' ? t('reminders.digestDailyShort') : ''
  const parts = [typeName, subLabel]
  if (digestLabel) parts.push(digestLabel)
  return parts.join(' · ')
}

onMounted(async () => {
  channels.value = await notificationChannelsApi.list()
})

function openAdd() {
  editingChannel.value = null
  resetForm()
  showSheet.value = true
}

function editChannel(channel: NotificationChannelResponse) {
  editingChannel.value = channel
  form.name = channel.name
  form.channel_type = channel.channel_type
  form.subscriptions = [...channel.subscriptions]
  form.digestEnabled = channel.digest_mode === 'daily'
  form.digest_time = channel.digest_time || '21:00'
  // Populate config fields from decrypted config
  const cfg = channel.config || {}
  if (channel.channel_type === 'telegram') {
    form.bot_token = String(cfg.bot_token || '')
    form.chat_id = String(cfg.chat_id || '')
    const mc = (cfg.mention_config || {}) as Record<string, string>
    form.mention_username = String(mc.username || '')
    form.mention_user_id = String(mc.user_id || '')
  } else if (channel.channel_type === 'feishu') {
    form.webhook_url = String(cfg.webhook_url || '')
    form.secret = String(cfg.secret || '')
    const mc = (cfg.mention_config || {}) as Record<string, string>
    form.mention_name = String(mc.name || '')
    form.mention_open_id = String(mc.open_id || '')
  } else if (channel.channel_type === 'email') {
    form.smtp_host = String(cfg.smtp_host || '')
    form.smtp_port = typeof cfg.smtp_port === 'number' ? cfg.smtp_port : parseInt(String(cfg.smtp_port || '587')) || 587
    form.smtp_user = String(cfg.smtp_user || '')
    form.smtp_password = String(cfg.smtp_password || '')
    form.smtp_from = String(cfg.smtp_from || '')
    form.email_to = String(cfg.to || '')
  }
  showSheet.value = true
}

function onEventsSaved(types: string[]) {
  form.subscriptions = types
}

function onTimeConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.digest_time = `${selectedValues[0]}:${selectedValues[1]}`
  showTimePicker.value = false
}

async function saveChannel() {
  if (!form.name.trim()) {
    showToast(t('reminders.channelNameRequired'))
    return
  }
  if (form.channel_type === 'telegram' && !form.chat_id.trim()) {
    showToast(t('reminders.chatIdRequired'))
    return
  }
  if (form.channel_type === 'telegram' && !/^-?\d+$/.test(form.chat_id)) {
    showToast(t('reminders.chatIdInvalid'))
    return
  }
  if (form.channel_type === 'email' && !form.smtp_host.trim()) {
    showToast(t('reminders.smtpHostRequired'))
    return
  }
  if (form.channel_type === 'feishu' && !form.webhook_url.trim()) {
    showToast(t('reminders.webhookUrlRequired'))
    return
  }

  const config: Record<string, string | number | Record<string, string>> =
    form.channel_type === 'telegram'
      ? { bot_token: form.bot_token, chat_id: form.chat_id }
      : form.channel_type === 'feishu'
      ? { webhook_url: form.webhook_url, secret: form.secret }
      : {
          smtp_host: form.smtp_host,
          smtp_port: typeof form.smtp_port === 'number' ? form.smtp_port : parseInt(form.smtp_port) || 587,
          smtp_user: form.smtp_user,
          smtp_password: form.smtp_password,
          smtp_from: form.smtp_from,
          to: form.email_to,
        }

  // Attach mention_config for telegram / feishu
  if (form.channel_type === 'telegram' && (form.mention_username || form.mention_user_id)) {
    config.mention_config = {
      username: form.mention_username,
      user_id: form.mention_user_id,
    }
  } else if (form.channel_type === 'feishu' && (form.mention_name || form.mention_open_id)) {
    config.mention_config = {
      name: form.mention_name,
      open_id: form.mention_open_id,
    }
  }

  const digestMode = form.digestEnabled ? 'daily' : 'immediate'

  if (editingChannel.value) {
    const updated = await notificationChannelsApi.update(editingChannel.value.id, {
      name: form.name,
      config,
      subscriptions: form.subscriptions,
      digest_mode: digestMode,
      digest_time: form.digest_time,
    })
    const idx = channels.value.findIndex((c) => c.id === editingChannel.value!.id)
    if (idx >= 0) channels.value[idx] = updated
  } else {
    const created = await notificationChannelsApi.create({
      channel_type: form.channel_type,
      name: form.name,
      config,
      is_enabled: true,
      subscriptions: form.subscriptions,
      digest_mode: digestMode,
      digest_time: form.digest_time,
    })
    channels.value.push(created)
  }
  showSuccessToast(t('toast.channelSaved'))
  showSheet.value = false
  editingChannel.value = null
}

async function removeChannel(id: string) {
  await notificationChannelsApi.remove(id)
  channels.value = channels.value.filter((c) => c.id !== id)
  showSuccessToast(t('toast.channelDeleted'))
}

function onTypeConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.channel_type = selectedValues[0] as 'telegram' | 'email' | 'feishu'
  showTypePicker.value = false
}
</script>

<style scoped>
.page-content {
  padding-bottom: 32px;
}
.section {
  margin-top: 12px;
}
.delete-btn {
  height: 100%;
}
.popup-content {
  height: 100%;
  overflow-y: auto;
}
</style>
