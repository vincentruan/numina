<template>
  <CeremonyRoom @close="router.back()">
    <div v-if="templateId" class="preview-layout">
      <!-- TOC sidebar: shows trackable clauses -->
      <aside v-if="clauses.length > 0" class="preview-toc">
        <div class="toc-header">
          <span class="toc-icon">📜</span>
          <span class="toc-title">{{ t('manifesto.clausesTitle') }}</span>
        </div>
        <ul class="toc-list">
          <li
            v-for="(clause, idx) in clauses"
            :key="idx"
            class="toc-item"
            :class="{ active: activeClause === idx }"
            @click="scrollToClause(idx)"
          >
            <span class="toc-num">{{ clause.globalIndex + 1 }}</span>
            <span class="toc-text">{{ clause.firstLine }}</span>
          </li>
        </ul>
      </aside>

      <!-- Main content area -->
      <div class="preview-main">
        <div class="preview-certificate">
          <ManifestoViewer
            :template-id="templateId"
            :title="state.title"
            :body="body"
            :signatures="signatures"
            :members="members"
          />
        </div>

        <!-- Scroll hint -->
        <div v-if="!reachedBottom" class="preview-scroll-hint">
          <van-icon name="arrow-down" />
          <span>{{ t('manifesto.scrollToPublish') }}</span>
        </div>

        <!-- Publish action -->
        <div class="preview-actions">
          <div class="publish-info">
            <van-icon name="info-o" />
            <span>{{ t('manifesto.previewHint') }}</span>
          </div>
          <van-button type="primary" block size="large" :loading="publishing" @click="onPublish">
            {{ t('manifesto.publish') }}
          </van-button>
        </div>
      </div>
    </div>

    <van-action-sheet
      v-model:show="showChangeTypeSheet"
      :title="t('manifesto.changeTypeTitle')"
      :actions="changeTypeActions"
      @select="onChangeTypeSelect"
    />
  </CeremonyRoom>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import ManifestoViewer from '@/components/manifesto/ManifestoViewer.vue'
import CeremonyRoom from '@/components/manifesto/CeremonyRoom.vue'
import { useCeremonyRoom } from '@/composables/useCeremonyRoom'
import { useManifestoWizard } from '@/composables/useManifestoWizard'
import { useFamilyStore } from '@/stores/family'
import * as manifestoApi from '@/api/manifesto'

const { t } = useI18n()
const router = useRouter()
useCeremonyRoom(() => router.back())
const { state, reset } = useManifestoWizard()
const familyStore = useFamilyStore()

const publishing = ref(false)
const showChangeTypeSheet = ref(false)
const existingManifestoId = ref<string | null>(null)
const reachedBottom = ref(false)
const activeClause = ref<number | null>(null)

interface ClauseItem {
  globalIndex: number
  firstLine: string
}

onMounted(async () => {
  if (!state.value.selectedTemplateId) {
    router.replace('/manifesto/template-select')
    return
  }
  if (familyStore.members.length === 0) {
    try {
      await familyStore.fetchFamily()
    } catch {
      // ignore — preview still works with empty members
    }
  }
  // Check if a manifesto already exists (edit vs create)
  try {
    const res = await manifestoApi.getCurrentManifesto()
    existingManifestoId.value = res.data.id
  } catch {
    existingManifestoId.value = null
  }

  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
})

const templateId = computed(() => state.value.selectedTemplateId ?? '')

const body = computed(() => {
  if (state.value.body) return state.value.body
  return state.value.blocks.filter((b: string) => b.trim()).join('\n\n')
})

const bodyParagraphs = computed(() =>
  body.value.split('\n\n').filter(p => p.trim()),
)

/** Extract trackable clauses: numbered first-lines of trackable paragraphs. */
const clauses = computed<ClauseItem[]>(() => {
  const indices = state.value.trackableIndices ?? []
  return indices
    .filter(i => i < bodyParagraphs.value.length)
    .map((globalIndex) => {
      const text = bodyParagraphs.value[globalIndex]
      const firstLine = text.split('\n')[0]?.trim().slice(0, 20) ?? ''
      return { globalIndex, firstLine }
    })
})

// Preview shows all members as unsigned (no one has signed the new version yet)
const signatures = computed(() =>
  familyStore.members.map(m => ({ name: m.display_name, data: undefined })),
)

const members = computed(() =>
  familyStore.members.map(m => ({ name: m.display_name, role: m.role })),
)

const changeTypeActions = computed(() => [
  {
    name: t('manifesto.minorUpdate'),
    subname: t('manifesto.minorHint'),
    value: 'minor',
  },
  {
    name: t('manifesto.majorUpdate'),
    subname: t('manifesto.majorHint'),
    value: 'major',
  },
])

function onScroll() {
  const scrollTop = window.scrollY
  const docHeight = document.documentElement.scrollHeight
  const winHeight = window.innerHeight
  reachedBottom.value = scrollTop + winHeight >= docHeight - 80

  // Determine active clause by scroll position
  if (clauses.value.length === 0) return
  const paragraphEls = document.querySelectorAll('.manifesto-viewer p')
  let current: number | null = null
  for (let i = 0; i < clauses.value.length; i++) {
    const globalIdx = clauses.value[i].globalIndex
    const el = paragraphEls[globalIdx]
    if (el && el.getBoundingClientRect().top <= 120) {
      current = i
    }
  }
  activeClause.value = current
}

function scrollToClause(idx: number) {
  const globalIdx = clauses.value[idx]?.globalIndex
  if (globalIdx == null) return
  const paragraphEls = document.querySelectorAll('.manifesto-viewer p')
  const el = paragraphEls[globalIdx]
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function onPublish() {
  if (existingManifestoId.value) {
    showChangeTypeSheet.value = true
  } else {
    doCreate()
  }
}

async function doCreate() {
  publishing.value = true
  try {
    await manifestoApi.createManifesto({
      template_id: templateId.value,
      title: state.value.title,
      body: body.value,
      change_type: 'initial',
      trackable_clause_indices: state.value.trackableIndices.length > 0 ? state.value.trackableIndices : null,
      signing_deadline: state.value.signingDeadline,
    })
    reset()
    router.replace('/settings')
    showSuccessToast(t('manifesto.publishSuccess'))
  } catch {
    showFailToast(t('manifesto.publishFailed'))
  } finally {
    publishing.value = false
  }
}

async function onChangeTypeSelect(action: { value: string }) {
  showChangeTypeSheet.value = false
  publishing.value = true
  try {
    await manifestoApi.publishUpdate({
      template_id: templateId.value,
      title: state.value.title,
      body: body.value,
      change_type: action.value as 'minor' | 'major',
      trackable_clause_indices: state.value.trackableIndices.length > 0 ? state.value.trackableIndices : null,
      signing_deadline: state.value.signingDeadline,
    })
    reset()
    router.replace('/settings')
    showSuccessToast(t('manifesto.publishSuccess'))
  } catch {
    showFailToast(t('manifesto.publishFailed'))
  } finally {
    publishing.value = false
  }
}
</script>

<style scoped>
/* ── Two-column layout ── */
.preview-layout {
  display: flex;
  gap: 0;
  min-height: calc(100vh - 46px);
}

/* ── TOC Sidebar ── */
.preview-toc {
  position: sticky;
  top: 46px;
  width: 160px;
  flex-shrink: 0;
  padding: 16px 12px;
  border-right: 1px solid var(--color-border, #f0f0f0);
  background: var(--bg-primary, #fff);
  align-self: flex-start;
  max-height: calc(100vh - 46px);
  overflow-y: auto;
}

.toc-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border, #f0f0f0);
}

.toc-icon {
  font-size: 14px;
}

.toc-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #616161);
  letter-spacing: 0.02em;
}

.toc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.toc-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.toc-item:active {
  background: var(--card-bg, #f5f5ff);
}

.toc-item.active {
  background: rgba(201, 168, 76, 0.1);
}

.toc-num {
  font-size: 12px;
  font-weight: 700;
  color: #c9a84c;
  flex-shrink: 0;
  min-width: 16px;
}

.toc-text {
  font-size: 12px;
  color: var(--text-primary, #0a0a0a);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toc-item.active .toc-text {
  font-weight: 600;
}

/* ── Main content ── */
.preview-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.preview-certificate {
  padding: 16px;
}

/* ── Scroll hint ── */
.preview-scroll-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--text-secondary, #616161);
  animation: hintPulse 2s ease-in-out infinite;
}

@keyframes hintPulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* ── Publish actions ── */
.preview-actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.publish-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #616161);
}
</style>
