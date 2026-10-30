<template>
  <van-nav-bar
    :title="t('reminders.notificationSettings')"
    left-arrow
    @click-left="$router.back()"
  />

  <div class="page-content">
    <!-- Large-purchase linkage hint -->
    <div v-if="largePurchaseHint" class="linkage-hint">
      <van-notice-bar
        :text="largePurchaseHint.text"
        :type="largePurchaseHint.type"
        left-icon="info-o"
        :clickable="!!largePurchaseHint.action"
        @click="onLargePurchaseLinkClick"
      />
    </div>

    <van-cell-group inset :title="t('reminders.channelGroupTitle')" class="section">
      <van-swipe-cell v-for="channel in channels" :key="channel.id">
        <van-cell
          :title="channel.name"
          :label="channelLabel(channel)"
          is-link
          @click="editChannel(channel)"
        >
          <template #value>
            <div class="channel-status" @click.stop="openDeliveryHistory(channel, $event)">
              <span
                v-if="channel.last_delivery_status === 'sent'"
                class="status-dot status-dot--sent"
              />
              <span
                v-else-if="channel.last_delivery_status === 'failed'"
                class="status-dot status-dot--failed"
              />
              <span
                v-else
                class="status-dot status-dot--none"
              />
              <span class="status-text">{{ deliveryStatusText(channel) }}</span>
            </div>
          </template>
        </van-cell>
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

    <!-- Post-creation onboarding card -->
    <div v-if="showOnboarding && newChannel" class="onboarding-card">
      <div class="onboarding-card__header">
        <span>{{ t('reminders.onboardingTitle') }}</span>
        <van-icon name="cross" class="onboarding-card__close" @click="dismissOnboarding" />
      </div>
      <div class="onboarding-card__steps">
        <div class="onboarding-step" :class="{ 'onboarding-step--done': newChannel.subscriptions.length > 0 }">
          <span class="onboarding-step__icon">{{ newChannel.subscriptions.length > 0 ? '✅' : '1️⃣' }}</span>
          <span class="onboarding-step__label">{{ t('reminders.onboardingSubscribe') }}</span>
          <van-button v-if="!newChannel.subscriptions.length" size="mini" plain type="primary" @click="editChannel(newChannel)">{{ t('reminders.onboardingGo') }}</van-button>
        </div>
        <div v-if="showThresholdStep" class="onboarding-step" :class="{ 'onboarding-step--done': thresholdConfigured }">
          <span class="onboarding-step__icon">{{ thresholdConfigured ? '✅' : '2️⃣' }}</span>
          <span class="onboarding-step__label">{{ t('reminders.onboardingThreshold') }}</span>
          <van-button v-if="!thresholdConfigured" size="mini" plain type="primary" @click="router.push('/settings/notifications/threshold')">{{ t('reminders.onboardingGo') }}</van-button>
        </div>
        <div class="onboarding-step">
          <span class="onboarding-step__icon">3️⃣</span>
          <span class="onboarding-step__label">{{ t('reminders.onboardingTest') }}</span>
          <van-button size="mini" plain type="primary" :loading="testSending" @click="sendTestForOnboarding">{{ t('reminders.onboardingGo') }}</van-button>
        </div>
      </div>
    </div>
  </div>

  <van-popup v-model:show="showSheet" position="bottom" round teleport="body" :style="{ height: '80%' }">
    <div class="popup-content">
      <van-nav-bar :title="editingChannel ? t('reminders.editChannelTitle') : t('reminders.addChannelTitle')">
        <template #right>
          <van-button
            v-if="editingChannel"
            plain
            type="primary"
            size="small"
            :loading="testSending"
            :disabled="testSending"
            @click="sendTest"
          >
            {{ testSending ? t('reminders.testSending') : t('reminders.sendTest') }}
          </van-button>
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
        <template v-if="form.channel_type === 'webpush'">
          <van-cell :title="t('reminders.webpushHint')" />
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
          <div class="save-actions">
            <van-button type="primary" block @click="saveChannel()">{{ t('common.save') }}</van-button>
            <van-button
              v-if="editingChannel"
              plain
              type="success"
              block
              :loading="testSending"
              :disabled="testSending"
              class="save-actions__test"
              @click="saveAndTest"
            >
              {{ testSending ? t('reminders.testSending') : t('reminders.saveAndTest') }}
            </van-button>
          </div>
          <div v-if="testResult !== null" :class="['test-result', testResult.success ? 'test-result--success' : 'test-result--fail']">
            {{ testResult.success ? t('reminders.testSuccess') : t('reminders.testFailedWithReason', { reason: testResult.error || t('reminders.testFailed') }) }}
          </div>
        </van-cell>
      </van-cell-group>
    </div>
  </van-popup>

  <!-- Event selector popup -->
  <EventSelectorPopup
    v-model="showEventSelector"
    :initial-types="form.subscriptions"
    :event-availability="featureStatus?.event_availability"
    @save="onEventsSaved"
    @navigate-to-threshold="onNavigateToThreshold"
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

  <!-- Delivery history popup -->
  <van-popup v-model:show="showDeliveryHistory" position="bottom" round teleport="body" :style="{ height: '50%' }">
    <div class="popup-content">
      <van-nav-bar :title="t('reminders.deliveryHistory')">
        <template #right>
          <van-icon name="cross" @click="showDeliveryHistory = false" />
        </template>
      </van-nav-bar>
      <van-loading v-if="historyLoading" class="history-loading" />
      <EmptyState v-else-if="!deliveryHistory.length" :description="t('reminders.deliveryHistoryEmpty')" />
      <van-cell v-for="record in deliveryHistory" v-else :key="record.id" :title="record.reminder_title">
        <template #label>{{ t('reminders.types.' + record.reminder_type) }}</template>
        <template #value>
          <span :class="record.status === 'sent' ? 'delivery-status--sent' : 'delivery-status--failed'">
            {{ record.status === 'sent' ? t('reminders.deliveryStatusSent') : t('reminders.deliveryStatusFailed') }}
          </span>
        </template>
      </van-cell>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import {
  notificationChannelsApi,
  type NotificationChannelResponse,
  type NotificationChannelType,
  type ChannelTestResult,
  type DeliveryRecord,
  type NotificationFeatureStatus,
} from '@/api/notificationChannels'
import EventSelectorPopup from '@/components/notification/EventSelectorPopup.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { parseApiDate } from '@/utils/format'

const { t, locale } = useI18n()
const router = useRouter()

const channels = ref<NotificationChannelResponse[]>([])
const showSheet = ref(false)
const showTypePicker = ref(false)
const showEventSelector = ref(false)
const showMentionSheet = ref(false)
const showTimePicker = ref(false)
const showDeliveryHistory = ref(false)
const editingChannel = ref<NotificationChannelResponse | null>(null)
const testSending = ref(false)
const deliveryHistory = ref<DeliveryRecord[]>([])
const historyLoading = ref(false)
const featureStatus = ref<NotificationFeatureStatus | null>(null)
const showOnboarding = ref(false)
const newChannel = ref<NotificationChannelResponse | null>(null)
const testResult = ref<ChannelTestResult | null>(null)
let savedChannel: NotificationChannelResponse | null = null

const thresholdConfigured = computed(() => featureStatus.value?.large_purchase.threshold_configured ?? false)
const showThresholdStep = computed(
  () => newChannel.value?.subscriptions.includes('large_purchase') ?? false,
)

const typePickerColumns = computed(() => [
  { text: t('reminders.channelType.telegram'), value: 'telegram' },
  { text: t('reminders.channelType.email'), value: 'email' },
  { text: t('reminders.channelType.feishu'), value: 'feishu' },
  { text: t('reminders.channelType.webpush'), value: 'webpush' },
])

const form = reactive({
  name: '',
  channel_type: 'telegram' as NotificationChannelType,
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

/** Hint banner above the channel list about large-purchase linkage. */
const largePurchaseHint = computed(() => {
  const status = featureStatus.value?.large_purchase
  if (!status) return null
  const hasSubscription = channels.value.some((c) => c.subscriptions.includes('large_purchase'))
  if (status.threshold_configured && status.subscribing_channel_count > 0) {
    return {
      type: 'primary' as const,
      text: t('reminders.largePurchaseLinkageOk', { count: status.subscribing_channel_count }),
      action: undefined as 'threshold' | 'channels' | undefined,
    }
  }
  if (!status.threshold_configured && hasSubscription) {
    return {
      type: 'warning' as const,
      text: t('reminders.largePurchaseNoThreshold'),
      action: 'threshold' as const,
    }
  }
  if (status.threshold_configured && !hasSubscription) {
    return {
      type: 'warning' as const,
      text: t('reminders.largePurchaseNoChannel'),
      action: 'channels' as const,
    }
  }
  // Neither side configured — silent until one side is.
  return null
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

function deliveryStatusText(channel: NotificationChannelResponse): string {
  if (!channel.last_delivery_status || !channel.last_delivery_at) {
    return t('reminders.lastDeliveryNone')
  }
  const key =
    channel.last_delivery_status === 'sent'
      ? 'reminders.lastDeliverySuccess'
      : 'reminders.lastDeliveryFailed'
  const time = parseApiDate(channel.last_delivery_at).toLocaleString(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
  return t(key, { time })
}

async function openDeliveryHistory(channel: NotificationChannelResponse, ev: MouseEvent) {
  ev.stopPropagation()
  editingChannel.value = null
  deliveryHistory.value = []
  historyLoading.value = true
  showDeliveryHistory.value = true
  try {
    deliveryHistory.value = await notificationChannelsApi.getDeliveryHistory(channel.id)
  } catch {
    showFailToast(t('reminders.loadHistoryFailed'))
  } finally {
    historyLoading.value = false
  }
}

/**
 * Single owner of a channel test call. Callers differ only in presentation:
 * `toast` reports through Vant toasts, `inline` stores the result in
 * `testResult` for the form banner.
 */
async function runChannelTest(
  channelId: string,
  report: 'toast' | 'inline',
): Promise<ChannelTestResult> {
  testSending.value = true
  let result: ChannelTestResult
  try {
    result = await notificationChannelsApi.testChannel(channelId)
  } catch {
    result = { success: false, error: t('reminders.testFailed') }
  } finally {
    testSending.value = false
  }

  if (report === 'inline') {
    testResult.value = result
    return result
  }
  if (result.success) {
    showSuccessToast(t('reminders.testSuccess'))
  } else {
    showFailToast(
      result.error
        ? t('reminders.testFailedWithReason', { reason: result.error })
        : t('reminders.testFailed'),
    )
  }
  return result
}

async function sendTest() {
  if (!editingChannel.value) {
    showToast(t('reminders.saveBeforeTest'))
    return
  }
  await runChannelTest(editingChannel.value.id, 'toast')
}

function onLargePurchaseLinkClick() {
  const action = largePurchaseHint.value?.action
  if (action === 'threshold') {
    router.push('/settings/notifications/threshold')
  } else if (action === 'channels') {
    // Stay on this page — user just needs to subscribe a channel.
  }
}

function onNavigateToThreshold() {
  showEventSelector.value = false
  router.push('/settings/notifications/threshold')
}

const ONBOARDING_KEY = 'numina:notification-onboarding-channel'

async function refreshAll() {
  const [listed, status] = await Promise.all([
    notificationChannelsApi.list(),
    notificationChannelsApi.getFeatureStatus().catch(() => null),
  ])
  channels.value = listed
  featureStatus.value = status
  // The page remounts on every return (it is not a KeepAlive-cached tab), so
  // the onboarding card is restored from sessionStorage and re-bound to the
  // freshly listed record to keep its step states accurate.
  const pendingId = sessionStorage.getItem(ONBOARDING_KEY)
  if (pendingId) {
    const restored = listed.find((c) => c.id === pendingId)
    if (restored) {
      newChannel.value = restored
      showOnboarding.value = true
    } else {
      sessionStorage.removeItem(ONBOARDING_KEY)
    }
  }
}

function dismissOnboarding() {
  showOnboarding.value = false
  newChannel.value = null
  sessionStorage.removeItem(ONBOARDING_KEY)
}

onMounted(refreshAll)

function openAdd() {
  editingChannel.value = null
  resetForm()
  testResult.value = null
  showSheet.value = true
}

function editChannel(channel: NotificationChannelResponse) {
  editingChannel.value = channel
  testResult.value = null
  form.name = channel.name
  form.channel_type = channel.channel_type
  form.subscriptions = [...channel.subscriptions]
  form.digestEnabled = channel.digest_mode === 'daily'
  form.digest_time = channel.digest_time || '21:00'
  // Populate config fields from decrypted config. Masked sensitive values are
  // preserved verbatim so the save path sends them back for the backend to
  // keep the existing ciphertext.
  const cfg = channel.config || {}
  if (channel.channel_type === 'telegram') {
    form.bot_token = String(cfg.bot_token || '')
    form.chat_id = String(cfg.chat_id || '')
    const mc = cfg.mention_config as Record<string, string> | string | undefined
    if (mc && typeof mc === 'object') {
      form.mention_username = String(mc.username || '')
      form.mention_user_id = String(mc.user_id || '')
    }
  } else if (channel.channel_type === 'feishu') {
    form.webhook_url = String(cfg.webhook_url || '')
    form.secret = String(cfg.secret || '')
    const mc = cfg.mention_config as Record<string, string> | string | undefined
    if (mc && typeof mc === 'object') {
      form.mention_name = String(mc.name || '')
      form.mention_open_id = String(mc.open_id || '')
    }
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

async function saveChannel({
  keepSheetOpen = false,
}: { keepSheetOpen?: boolean } = {}): Promise<NotificationChannelResponse | null> {
  if (!form.name.trim()) {
    showToast(t('reminders.channelNameRequired'))
    return null
  }
  if (form.channel_type === 'telegram' && !form.chat_id.trim()) {
    showToast(t('reminders.chatIdRequired'))
    return null
  }
  if (form.channel_type === 'telegram' && !/^-?\d+$/.test(form.chat_id)) {
    showToast(t('reminders.chatIdInvalid'))
    return null
  }
  if (form.channel_type === 'email' && !form.smtp_host.trim()) {
    showToast(t('reminders.smtpHostRequired'))
    return null
  }
  if (form.channel_type === 'feishu' && !form.webhook_url.trim()) {
    showToast(t('reminders.webhookUrlRequired'))
    return null
  }

  const config: Record<string, string | number | Record<string, string>> =
    form.channel_type === 'telegram'
      ? { bot_token: form.bot_token, chat_id: form.chat_id }
      : form.channel_type === 'feishu'
      ? { webhook_url: form.webhook_url, secret: form.secret }
      : form.channel_type === 'email'
      ? {
          smtp_host: form.smtp_host,
          smtp_port: typeof form.smtp_port === 'number' ? form.smtp_port : parseInt(form.smtp_port) || 587,
          smtp_user: form.smtp_user,
          smtp_password: form.smtp_password,
          smtp_from: form.smtp_from,
          to: form.email_to,
        }
      : {} // webpush has no user-configurable config

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
    savedChannel = updated
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
    // Show onboarding card for new channels; it survives the remount that
    // happens when the user navigates to the threshold page and back.
    newChannel.value = created
    showOnboarding.value = true
    sessionStorage.setItem(ONBOARDING_KEY, created.id)
    savedChannel = created
  }
  testResult.value = null
  showSuccessToast(t('toast.channelSaved'))
  if (!keepSheetOpen) {
    showSheet.value = false
    editingChannel.value = null
  }
  return savedChannel
}

async function saveAndTest() {
  // Keep the sheet open so the inline result banner is actually visible.
  const target = await saveChannel({ keepSheetOpen: true })
  if (!target) return
  testSending.value = true
  testResult.value = null
  try {
    const result = await notificationChannelsApi.testChannel(target.id)
    testResult.value = result
  } catch {
    testResult.value = { success: false, error: t('reminders.testFailed') }
  } finally {
    testSending.value = false
  }
}

async function sendTestForOnboarding() {
  if (!newChannel.value) return
  await runChannelTest(newChannel.value.id, 'toast')
}

async function removeChannel(id: string) {
  await notificationChannelsApi.remove(id)
  channels.value = channels.value.filter((c) => c.id !== id)
  showSuccessToast(t('toast.channelDeleted'))
}

function onTypeConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.channel_type = selectedValues[0] as NotificationChannelType
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
.linkage-hint {
  margin: 8px 16px 0;
}
.channel-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  cursor: pointer;
  min-width: 80px;
}
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot--sent {
  background: var(--van-success-color);
}
.status-dot--failed {
  background: var(--van-danger-color);
}
.status-dot--none {
  background: var(--van-gray-4);
}
.status-text {
  font-size: 11px;
  color: var(--van-text-color-3);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.delivery-status--sent {
  color: var(--van-success-color);
  font-size: 12px;
}
.delivery-status--failed {
  color: var(--van-danger-color);
  font-size: 12px;
}
.history-loading {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}
.save-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.save-actions__test {
  margin-top: 0;
}
.test-result {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
}
.test-result--success {
  background: rgba(0, 200, 0, 0.08);
  color: var(--van-success-color);
}
.test-result--fail {
  background: rgba(255, 0, 0, 0.06);
  color: var(--van-danger-color);
}
.onboarding-card {
  margin: 12px 16px;
  padding: 12px 16px;
  background: var(--van-background-2);
  border-radius: 8px;
  border: 1px solid var(--van-primary-color);
}
.onboarding-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
}
.onboarding-card__close {
  cursor: pointer;
  color: var(--van-text-color-2);
}
.onboarding-card__steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.onboarding-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.onboarding-step--done {
  opacity: 0.6;
}
.onboarding-step__icon {
  flex-shrink: 0;
}
.onboarding-step__label {
  flex: 1;
}
</style>
