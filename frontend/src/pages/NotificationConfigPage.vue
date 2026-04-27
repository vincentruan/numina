<template>
  <van-nav-bar
    :title="t('reminders.notificationSettings')"
    left-arrow
    @click-left="$router.back()"
  />

  <div class="page-content">
    <van-cell-group inset title="大额消费阈值" class="section">
      <van-field
        v-model="fixedThreshold"
        :label="t('reminders.thresholdFixed')"
        type="number"
        placeholder="如 5000"
        clearable
      />
      <van-field
        v-model="multiplierThreshold"
        :label="t('reminders.thresholdMultiplier')"
        type="number"
        placeholder="如 2"
        clearable
      />
      <van-cell>
        <van-button type="primary" size="small" block @click="saveConfig">保存阈值配置</van-button>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset title="通知渠道" class="section">
      <van-swipe-cell v-for="channel in channels" :key="channel.id">
        <van-cell
          :title="channel.name"
          :label="`${t('reminders.channelType.' + channel.channel_type)} · ${channel.subscriptions.map((s) => t('reminders.types.' + s)).join('、')}`"
          :value="channel.is_enabled ? '已启用' : '已停用'"
          is-link
          @click="editChannel(channel)"
        />
        <template #right>
          <van-button
            square
            type="danger"
            text="删除"
            class="delete-btn"
            @click="removeChannel(channel.id)"
          />
        </template>
      </van-swipe-cell>
      <van-cell title="添加渠道" is-link icon="plus" @click="openAdd" />
    </van-cell-group>
  </div>

  <van-popup v-model:show="showSheet" position="bottom" round :style="{ height: '75%' }">
    <div class="popup-content">
      <van-nav-bar :title="editingChannel ? '编辑渠道' : '添加渠道'">
        <template #right>
          <van-icon name="cross" @click="showSheet = false" />
        </template>
      </van-nav-bar>
      <van-cell-group inset>
        <van-field v-model="form.name" label="渠道名称" placeholder="如：家庭群" />
        <van-field
          v-if="!editingChannel"
          :model-value="t('reminders.channelType.' + form.channel_type)"
          label="渠道类型"
          readonly
          is-link
          @click="showTypePicker = true"
        />
        <template v-if="form.channel_type === 'telegram'">
          <van-field v-model="form.bot_token" label="Bot Token" placeholder="从 @BotFather 获取" type="password" />
          <van-field v-model="form.chat_id" label="Chat ID" placeholder="数字 ID" />
        </template>
        <template v-if="form.channel_type === 'email'">
          <van-field v-model="form.smtp_host" label="SMTP 服务器" placeholder="smtp.example.com" />
          <van-field v-model="form.smtp_port" label="端口" type="number" placeholder="587" />
          <van-field v-model="form.smtp_user" label="用户名" />
          <van-field v-model="form.smtp_password" label="密码" type="password" />
          <van-field v-model="form.smtp_from" label="发件人" placeholder="from@example.com" />
          <van-field v-model="form.email_to" label="收件人" placeholder="to@example.com" />
        </template>
        <van-cell :title="t('reminders.subscriptions')">
          <template #value>
            <van-checkbox-group v-model="form.subscriptions" direction="horizontal">
              <van-checkbox
                v-for="type in reminderTypes"
                :key="type"
                :name="type"
                shape="square"
                style="margin: 4px"
              >
                {{ t('reminders.types.' + type) }}
              </van-checkbox>
            </van-checkbox-group>
          </template>
        </van-cell>
        <van-cell>
          <van-button type="primary" block @click="saveChannel">保存</van-button>
        </van-cell>
      </van-cell-group>
    </div>
  </van-popup>

  <van-popup v-model:show="showTypePicker" position="bottom" round>
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
import { showToast } from 'vant'
import {
  notificationChannelsApi,
  type NotificationChannelResponse,
} from '@/api/notificationChannels'

const { t } = useI18n()

const channels = ref<NotificationChannelResponse[]>([])
const fixedThreshold = ref('')
const multiplierThreshold = ref('')
const showSheet = ref(false)
const showTypePicker = ref(false)
const editingChannel = ref<NotificationChannelResponse | null>(null)

const reminderTypes = ['large_purchase', 'allocation_drift', 'expiring_soon', 'maturity']

const typePickerColumns = computed(() => [
  { text: t('reminders.channelType.telegram'), value: 'telegram' },
  { text: t('reminders.channelType.email'), value: 'email' },
])

const form = reactive({
  name: '',
  channel_type: 'telegram' as 'telegram' | 'email',
  bot_token: '',
  chat_id: '',
  smtp_host: '',
  smtp_port: '587',
  smtp_user: '',
  smtp_password: '',
  smtp_from: '',
  email_to: '',
  subscriptions: [] as string[],
})

function resetForm() {
  form.name = ''
  form.channel_type = 'telegram'
  form.bot_token = ''
  form.chat_id = ''
  form.smtp_host = ''
  form.smtp_port = '587'
  form.smtp_user = ''
  form.smtp_password = ''
  form.smtp_from = ''
  form.email_to = ''
  form.subscriptions = []
}

onMounted(async () => {
  channels.value = await notificationChannelsApi.list()
  const config = await notificationChannelsApi.getConfig()
  fixedThreshold.value = config.large_purchase_threshold_fixed?.toString() ?? ''
  multiplierThreshold.value = config.large_purchase_threshold_multiplier?.toString() ?? ''
})

async function saveConfig() {
  await notificationChannelsApi.updateConfig({
    large_purchase_threshold_fixed: fixedThreshold.value ? parseFloat(fixedThreshold.value) : null,
    large_purchase_threshold_multiplier: multiplierThreshold.value
      ? parseFloat(multiplierThreshold.value)
      : null,
  })
  showToast(t('toast.configSaved'))
}

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
  showSheet.value = true
}

async function saveChannel() {
  if (form.channel_type === 'telegram' && !/^-?\d+$/.test(form.chat_id)) {
    showToast('⚠️ Chat ID 必须为数字')
    return
  }
  const config: Record<string, string | number> =
    form.channel_type === 'telegram'
      ? { bot_token: form.bot_token, chat_id: form.chat_id }
      : {
          smtp_host: form.smtp_host,
          smtp_port: parseInt(form.smtp_port),
          smtp_user: form.smtp_user,
          smtp_password: form.smtp_password,
          smtp_from: form.smtp_from,
          to: form.email_to,
        }

  if (editingChannel.value) {
    const updated = await notificationChannelsApi.update(editingChannel.value.id, {
      name: form.name,
      config,
      subscriptions: form.subscriptions,
    })
    const idx = channels.value.findIndex((c) => c.id === editingChannel.value!.id)
    if (idx >= 0) channels.value[idx] = updated
  } else {
    const created = await notificationChannelsApi.create({
      channel_type: form.channel_type,
      name: form.name,
      config,
      subscriptions: form.subscriptions,
    })
    channels.value.push(created)
  }
  showToast(t('toast.channelSaved'))
  showSheet.value = false
  editingChannel.value = null
}

async function removeChannel(id: number) {
  await notificationChannelsApi.remove(id)
  channels.value = channels.value.filter((c) => c.id !== id)
  showToast(t('toast.channelDeleted'))
}

function onTypeConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.channel_type = selectedValues[0] as 'telegram' | 'email'
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
