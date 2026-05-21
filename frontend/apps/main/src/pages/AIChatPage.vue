<template>
  <div class="ai-chat-page" :class="{ 'theme-light': isLight }">
    <!-- Fixed top bar: [back] [history/sidebar] [title] [new chat] -->
    <div class="chat-header">
      <button class="header-btn" :aria-label="t('common.back')" @click="router.back()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      <button class="header-btn" :aria-label="t('aiChat.historyAria')" @click="showHistory = true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <div class="header-title-wrap">
        <h1 class="header-title">{{ displayedTitle }}</h1>
        <button
          v-if="sessionTitle && sessionTitle !== t('aiChat.newChat')"
          class="header-edit-btn"
          :aria-label="t('aiChat.editTitle')"
          @click="onEditTitle"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
      </div>
      <div class="header-actions">
        <button class="header-btn" :aria-label="t('aiChat.newChatAria')" @click="onNewChat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- History sidebar drawer -->
    <van-popup v-model:show="showHistory" position="left" :style="{ width: '66%', height: '100%' }">
      <div class="history-panel">
        <div class="history-header">
          <button class="header-btn" :aria-label="t('aiChat.backAria')" @click="showHistory = false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <span class="history-title">{{ t('aiChat.historyTitle') }}</span>
        </div>
        <!-- Capability filter tabs -->
        <div class="history-filter">
          <button
            v-for="f in capabilityFilters"
            :key="f.value ?? 'all'"
            class="filter-tab"
            :class="{ 'filter-tab--active': f.value === null ? selectedCapability === 'all' : selectedCapability === f.value }"
            @click="onSelectCapability(f.value)"
          >{{ f.label }}</button>
        </div>
        <div v-if="sessionsLoading" class="history-empty">
          <p>{{ t('aiChat.loadingHistory') }}</p>
        </div>
        <div v-else-if="sessions.length === 0" class="history-empty">
          <p>{{ t('aiChat.noHistory') }}</p>
          <p class="history-hint">{{ t('aiChat.historyHint') }}</p>
        </div>
        <div v-else ref="historyScrollRef" class="history-scroll">
          <template v-for="group in groupedSessions" :key="group.label">
            <div class="history-group-label">{{ group.label }}</div>
            <ul class="history-list">
              <li
                v-for="session in group.sessions"
                :key="session.session_id"
                class="history-item"
                :class="{ 'history-item--active': session.session_id === currentSessionId }"
                @click="loadSessionMessages(session)"
              >
                <span class="history-item-title">{{ session.title ?? t('aiChat.untitledSession') }}</span>
                <button
                  class="history-item-menu-btn"
                  :aria-label="t('aiChat.moreActionsAria')"
                  @click.stop="openSessionMenu(session, $event)"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                  </svg>
                </button>
              </li>
            </ul>
          </template>
          <!-- Pagination sentinel -->
          <div ref="paginationSentinelRef" class="history-pagination-sentinel">
            <span v-if="sessionsLoadingMore" class="history-load-more-text">{{ t('aiChat.loadingMore') }}</span>
            <span v-else-if="sessionsAllLoaded" class="history-load-more-text">{{ t('aiChat.noMoreSessions') }}</span>
          </div>
        </div>

        <!-- Session context menu — inside popup to share stacking context -->
        <div
          v-if="sessionMenu.visible"
          class="session-menu-backdrop"
          @click="closeSessionMenu"
        />
        <div
          v-if="sessionMenu.visible"
          class="session-menu"
          :style="{ top: sessionMenu.y + 'px', left: sessionMenu.x + 'px' }"
        >
      <button class="session-menu-item" @click="onRenameSession">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
        <span>{{ t('aiChat.renameSession') }}</span>
      </button>
      <button class="session-menu-item" @click="onTogglePinSession">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/>
        </svg>
        <span>{{ sessionMenu.session?.is_pinned ? t('aiChat.unpinSession') : t('aiChat.pinSession') }}</span>
      </button>
      <button class="session-menu-item session-menu-item--danger" @click="onDeleteSession">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
        </svg>
        <span>{{ t('aiChat.deleteSession') }}</span>
      </button>
        </div>
        <!-- /session-menu -->
      </div>
    </van-popup>

    <!-- Rename session dialog -->
    <van-dialog
      v-model:show="showRenameDialog"
      :title="t('aiChat.renameSession')"
      show-cancel-button
      @confirm="onConfirmRename"
      @cancel="showRenameDialog = false"
    >
      <div style="padding: 16px 16px 8px">
        <van-field
          v-model="renameInput"
          :placeholder="t('aiChat.editTitlePlaceholder')"
          autofocus
          clearable
          maxlength="50"
          show-word-limit
        />
      </div>
    </van-dialog>

    <!-- Chat body -->
    <div ref="scrollRef" class="chat-body">

      <!-- Empty state: hero + suggestion cards -->
      <div v-if="!messages.length" class="chat-empty">
        <div class="empty-hero" aria-hidden="true">
          <div class="hero-glow" />
          <svg class="hero-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
            <path d="M810.161862 222.967283a13.594179 13.594179 0 0 0-13.594179-13.594179H696.289285a13.594179 13.594179 0 0 0-13.594179 13.594179v71.21302h127.523635V222.967283zM810.161862 337.693051H682.638227v146.180081l127.523635 220.862745V337.693051zM417.864578 71.156141c76.218408 11.887796 155.565184 49.883242 229.337777 109.947897a13.651058 13.651058 0 0 0 19.168361-1.990779 13.651058 13.651058 0 0 0-1.9339-19.168361C586.853302 96.865634 503.126812 56.879409 422.130534 44.25218a13.651058 13.651058 0 0 0-4.265956 26.903961z"/>
            <path d="M856.063545 396.165084a13.651058 13.651058 0 0 0-24.05999 12.740987c117.512859 222.057213 100.733433 458.334278-39.019275 549.739488-74.341388 48.575015-173.1978 50.736433-278.367827 6.029217-86.513581-36.800978-168.590568-101.643504-236.504583-185.768149l18.087652-31.454313h241.168694a6.029217 6.029217 0 0 0 5.232906-9.100706l-45.27601-78.322946a14.959285 14.959285 0 0 0-12.911625-7.394323H351.031273l109.037827-188.839638 221.488418 383.651614a13.992335 13.992335 0 0 0 12.172194 7.053046h114.441371c10.807088 0 17.632617-11.717158 12.172193-21.045381l-10.067655-17.518858-127.523635-220.862745L472.184414 230.475365a14.049214 14.049214 0 0 0-24.344387 0l-248.392379 430.23585C97.007832 470.847748 89.49975 262.78287 186.251625 148.625896a13.651058 13.651058 0 0 0-20.817864-17.632617c-106.364495 125.419097-97.150031 353.789924 18.087652 557.19069l-83.783369 145.156252a14.049214 14.049214 0 0 0 12.172193 21.102261h114.441371c5.005388 0 9.6695-2.673332 12.172194-7.053047l25.02694-43.34211c69.392879 83.669611 152.664334 148.284619 240.486141 185.597512 53.694162 22.865522 106.193857 34.241404 155.223907 34.241404 54.774871 0 105.283786-14.219852 148.682775-42.545798 74.853302-48.916292 120.470588-136.226185 128.376826-245.662167 7.7356-106.648892-20.817864-227.233239-80.256846-339.570072z"/>
            <path d="M280.842082 142.539799l14.39049 40.896295 14.390491-40.896295c5.972338-17.063823 19.338999-30.373604 36.402822-36.402822L386.8653 91.746487l-40.953174-14.390491c-17.006943-5.972338-30.373604-19.338999-36.402822-36.402822L295.289452 0.056879l-14.390491 40.953175c-6.029217 17.006943-19.338999 30.373604-36.402821 36.345942l-40.953175 14.390491 40.953175 14.39049c16.950064 6.029217 30.373604 19.395878 36.402821 36.402822z"/>
          </svg>
        </div>
        <p class="empty-title">{{ t('aiChat.greetingTitle') }}</p>
        <p class="empty-subtitle">{{ t('aiChat.greetingSubtitle') }}</p>

        <!-- Suggestion cards -->
        <div class="suggestion-grid">
          <button
            v-for="s in suggestions"
            :key="s.text"
            class="suggestion-card"
            @click="onChipClick(s.text)"
          >
            <span class="suggestion-icon" aria-hidden="true">
              <svg :viewBox="s.icon.viewBox" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path v-for="(d, i) in s.icon.paths" :key="i" :d="d" />
              </svg>
            </span>
            <span class="suggestion-text">{{ s.text }}</span>
            <span class="suggestion-arrow" aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </span>
          </button>
        </div>
      </div>

      <!-- Messages -->
      <template v-else>
        <transition-group name="msg" tag="div" class="msg-list">
          <div
            v-for="(msg, idx) in messages"
            :key="msg.id"
            class="message-row"
            :class="msg.role"
          >
            <div class="bubble" :class="[msg.role, { 'assistant--thinking': msg.role === 'assistant' && msg.phase && msg.phase !== 'done' && msg.phase !== 'error' }]">
              <div class="bubble-body">
                <!-- Connecting state region: shown while phase === 'connecting' -->
                <div
                  v-if="msg.role === 'assistant' && msg.phase === 'connecting'"
                  class="connecting-region shimmer-active"
                  aria-live="polite"
                >
                  <span class="connecting-dot" aria-hidden="true" />
                  <span class="connecting-label">{{ t('aiChat.connectingAI') }}</span>
                  <span class="connecting-sep" aria-hidden="true">·</span>
                  <span class="connecting-time">{{ connectingSeconds }}s</span>
                </div>
                <!-- Unified phase indicator: shown during thinking/answering when NOT deep think mode -->
                <div
                  v-if="msg.role === 'assistant' && msg.phase && msg.phase !== 'connecting' && msg.phase !== 'done' && msg.phase !== 'error' && !deepThink && msg.content"
                  class="phase-strip standalone"
                  :class="`phase-strip--${msg.phase}`"
                  aria-live="polite"
                >
                  <span class="phase-pulse" aria-hidden="true" />
                  <span class="phase-label">{{ phaseLabel(msg.phase) }}</span>
                </div>
                <!-- Deep think block with integrated phase indicator and tool timeline -->
                <div
                  v-if="msg.role === 'assistant' && (msg.thinkContent || msg.toolTimeline?.length || (msg.phase && msg.phase !== 'connecting' && msg.phase !== 'done' && msg.phase !== 'error' && deepThink))"
                  class="think-block"
                  :class="{
                    'think-block--open': msg.thinkOpen,
                    'think-block--done': msg.thinkDone,
                    'think-block--active': msg.phase && msg.phase !== 'connecting' && msg.phase !== 'done' && msg.phase !== 'error',
                    'shimmer-active': msg.phase && msg.phase !== 'connecting' && msg.phase !== 'done' && msg.phase !== 'error' && !msg.thinkDone,
                  }"
                >
                  <button class="think-toggle" @click="onThinkToggle(msg)">
                    <div class="think-icon-wrapper">
                      <span v-if="msg.phase && msg.phase !== 'connecting' && msg.phase !== 'done' && msg.phase !== 'error' && !msg.thinkDone" class="phase-pulse-small" aria-hidden="true" />
                      <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M9.663 17h4.673M12 3a6 6 0 0 1 6 6c0 2.22-1.2 4.16-3 5.2V16a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 12 3z"/>
                        <path d="M9 21h6"/>
                      </svg>
                    </div>
                    <span v-if="msg.thinkDone" class="think-status">{{ t('aiChat.thinkDone') }}</span>
                    <span v-else class="think-status think-status--active">
                      <span class="think-text-animated">{{ phaseLabel(msg.phase || 'thinking') }}</span>
                    </span>
                    <span v-if="msg.thinkDone" class="think-duration">{{ msg.thinkSeconds }}s</span>
                    <!-- Tool summary chips shown when collapsed -->
                    <template v-if="msg.thinkDone && !msg.thinkOpen && msg.toolTimeline?.length">
                      <span class="think-chip-sep" aria-hidden="true">·</span>
                      <span v-if="msg.toolTimeline.some(t => t.name === 'search' || t.icon === 'search')" class="think-chip">{{ t('aiChat.thinkSummarySearched') }}</span>
                      <span v-if="msg.toolTimeline.filter(t => t.name !== 'search' && t.icon !== 'search').length > 0" class="think-chip">{{ t('aiChat.thinkSummaryTools', { n: msg.toolTimeline.filter(t => t.name !== 'search' && t.icon !== 'search').length }) }}</span>
                    </template>
                    <svg class="think-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="6 9 12 15 18 9"/>
                    </svg>
                  </button>
                  <!-- Tool timeline inside think block (shown when expanded) -->
                  <div v-if="msg.thinkOpen && msg.toolTimeline?.length" class="tool-timeline">
                    <div
                      v-for="tool in msg.toolTimeline"
                      :key="tool.id"
                      class="tool-card"
                      :class="{ 'tool-card--done': tool.result, 'tool-card--error': tool.result && !tool.result.success, 'shimmer-active': !tool.result }"
                    >
                      <div class="tool-card-main">
                        <span class="tool-card-icon" aria-hidden="true">{{ toolIcon(tool.icon) }}</span>
                        <div class="tool-card-copy">
                          <span class="tool-card-title">{{ tool.displayName }}</span>
                          <span class="tool-card-meta">{{ toolStatus(tool) }}</span>
                        </div>
                      </div>
                      <div v-if="tool.argumentsText" class="tool-card-args">{{ tool.argumentsText }}</div>
                      <div v-if="tool.result && !tool.result.success" class="tool-result tool-result--failed">
                        {{ t('aiChat.toolCallFailed') }}
                      </div>
                      <div v-else-if="tool.result" class="tool-result">
                        {{ toolResultText(tool.result) }}
                      </div>
                    </div>
                  </div>
                  <!-- eslint-disable-next-line vue/no-v-html -- server-rendered markdown, not user-controlled HTML -->
                  <div v-if="msg.thinkOpen && msg.thinkContent" class="think-content" v-html="msg.thinkContent" />
                </div>
                <!-- eslint-disable vue/no-v-html -- server-rendered markdown, not user-controlled HTML -->
                <div
                  v-if="msg.role === 'assistant' && msg.phase !== 'error'"
                  class="bubble-text"
                  :class="{ 'bubble-text--appearing': msg.content && msg.phase === 'answering' && !msg.renderedContent }"
                  v-html="msg.renderedContent ?? ''"
                />
                <!-- Error state with retry button -->
                <div v-if="msg.role === 'assistant' && msg.phase === 'error'" class="error-state">
                  <p class="error-msg">{{ t('aiChat.errorRetry') }}</p>
                  <button class="error-retry-btn" :disabled="asking" @click="onRetryError(idx)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="1 4 1 10 7 10"/>
                      <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
                    </svg>
                    <span>{{ t('aiChat.retry') }}</span>
                  </button>
                </div>
                <!-- eslint-enable vue/no-v-html -->
                <div v-if="msg.role === 'user'" class="bubble-text">{{ msg.content }}</div>
                <span class="msg-time">{{ msg.displayTime }}</span>
                <!-- User message send status indicator -->
                <div v-if="msg.role === 'user' && msg.sendStatus === 'sending'" class="send-status send-status--sending" aria-live="polite">
                  <span class="send-status-dot" aria-hidden="true" />
                  <span>{{ t('aiChat.sendingMessage') }}</span>
                </div>
                <div v-if="msg.role === 'user' && msg.sendStatus === 'failed'" class="send-status send-status--failed" aria-live="polite">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  <span>{{ t('aiChat.sendFailed') }}</span>
                  <button class="send-retry-btn" :disabled="asking" @click="onRetrySend(idx)">{{ t('aiChat.resend') }}</button>
                </div>
                <!-- User message actions: copy + edit -->
                <div v-if="msg.role === 'user'" class="msg-actions msg-actions--user">
                  <button class="msg-action-btn" :aria-label="t('aiChat.copyAria')" :title="t('aiChat.copyAria')" @click="onCopy(msg.content)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                  <button class="msg-action-btn" :aria-label="t('aiChat.editAria')" :title="t('aiChat.editAria')" @click="onEditUserMessage(idx)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                </div>
                <!-- Streaming cursor: visible while answering -->
                <span v-if="msg.role === 'assistant' && msg.phase === 'answering'" class="stream-cursor" aria-hidden="true">▌</span>
                <!-- Interrupted hint -->
                <div v-if="msg.role === 'assistant' && msg.phase === 'interrupted'" class="interrupted-hint" aria-live="polite">
                  {{ t('aiChat.generationStopped') }}
                </div>
                <!-- Assistant message actions: only shown after generation completes/stops/fails -->
                <div v-if="msg.role === 'assistant' && (msg.phase === 'done' || msg.phase === 'interrupted' || msg.phase === 'error')" class="msg-actions">
                  <button class="msg-action-btn" :aria-label="t('aiChat.copyAria')" :title="t('aiChat.copyAria')" @click="onCopy(msg.content)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                  <button class="msg-action-btn" :aria-label="t('aiChat.regenerateAria')" :title="t('aiChat.regenerateAria')" :disabled="asking" @click="onRegenerate(idx)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="1 4 1 10 7 10"/>
                      <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
                    </svg>
                  </button>
                  <button
                    class="msg-action-btn"
                    :class="{ 'msg-action-btn--active': msg.feedback === 1 }"
                    :aria-label="t('aiChat.helpfulAria')"
                    :title="t('aiChat.helpfulAria')"
                    @click="onFeedback(msg.id, 1)"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
                      <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
                    </svg>
                  </button>
                  <button
                    class="msg-action-btn"
                    :class="{ 'msg-action-btn--active': msg.feedback === -1 }"
                    :aria-label="t('aiChat.notHelpfulAria')"
                    :title="t('aiChat.notHelpfulAria')"
                    @click="onFeedback(msg.id, -1)"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
                      <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </transition-group>

      </template>
    </div>

    <!-- Scroll-to-bottom floating button: shown when user scrolled up during streaming -->
    <transition name="scroll-btn">
      <button
        v-if="isUserScrolledUp && asking"
        class="scroll-to-bottom-btn"
        :aria-label="t('aiChat.scrollToBottom')"
        @click="onScrollToBottom"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
        <span>{{ t('aiChat.scrollToBottom') }}</span>
      </button>
    </transition>

    <!-- Input bar -->
    <div class="input-bar">
      <AIChatInput
        v-model="inputText"
        v-model:deep-think="deepThink"
        v-model:web-search="webSearch"
        :disabled="asking"
        :loading="asking || connecting"
        :show-clear="messages.length > 0"
        :placeholder="t('aiChat.inputPlaceholder')"
        @submit="onSend"
        @abort="onAbort"
        @action="onAction"
      />
    </div>

    <!-- Edit title dialog -->
    <van-dialog
      v-model:show="showEditTitleDialog"
      :title="t('aiChat.editTitle')"
      show-cancel-button
      @confirm="onConfirmEditTitle"
      @cancel="onCancelEditTitle"
    >
      <div style="padding: 16px 16px 8px">
        <van-field
          v-model="editTitleInput"
          :placeholder="t('aiChat.editTitlePlaceholder')"
          autofocus
          clearable
          maxlength="30"
          show-word-limit
        />
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { sendChatEventStream, getChatHistory, clearChatHistory, markChatRead } from '@/api/ai'
import { getSessions, streamSessionEvents, updateSession, deleteSession as deleteSessionApi } from '@/api/sessions'
import { useAIStore } from '@/stores/ai'
import AIChatInput from '@/components/common/AIChatInput.vue'
import { createAgentEventParser } from '@/composables/useAgentEventStream'
import type { AgentEvent } from '@/types/agent-stream'
import type { SessionSummary } from '@/types/session'

// Configure marked
marked.use({ breaks: true })

function renderMarkdown(text: string): string {
  return DOMPurify.sanitize(marked.parse(text) as string)
}

// Static data — module-level to avoid re-allocation on each mount
// Note: suggestions array is now computed to use i18n
const suggestions = computed(() => [
  {
    text: t('aiChat.suggestionAssetTotal'),
    icon: { viewBox: '0 0 24 24', paths: ['M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'] },
  },
  {
    text: t('aiChat.suggestionHighestCategory'),
    icon: { viewBox: '0 0 24 24', paths: ['M21.21 15.89A10 10 0 1 1 8 2.83', 'M22 12A10 10 0 0 0 12 2v10z'] },
  },
  {
    text: t('aiChat.suggestionIdleAssets'),
    icon: { viewBox: '0 0 24 24', paths: ['M20 7H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z', 'M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16'] },
  },
  {
    text: t('aiChat.suggestionNetWorthTrend'),
    icon: { viewBox: '0 0 24 24', paths: ['M23 6l-9.5 9.5-5-5L1 18', 'M17 6h6v6'] },
  },
])

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  sendStatus?: 'sending' | 'sent' | 'failed'
  content: string
  renderedContent?: string
  created_at: string
  displayTime: string
  feedback?: 1 | -1 | 0
  // deep think fields
  thinkContent?: string
  thinkOpen?: boolean
  thinkDone?: boolean
  thinkSeconds?: number
  thinkManuallyToggled?: boolean
  toolTimeline?: ToolTimelineItem[]
}

interface ToolTimelineItem {
  id: string
  name: string
  displayName: string
  icon: string
  argumentsText: string
  result?: {
    success?: boolean
    summary?: string
    data?: unknown
    error?: string
    execution_time_ms?: number
  }
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const aiStore = useAIStore()
const messages = ref<Message[]>([])
const inputText = ref('')
const asking = ref(false)
const connecting = ref(false)
const connectingSeconds = ref(0)
const deepThink = ref(false)
const webSearch = ref(false)
const scrollRef = ref<HTMLElement | null>(null)
const isUserScrolledUp = ref(false)
const showHistory = ref(false)
const sessions = ref<SessionSummary[]>([])
const sessionsLoading = ref(false)
const sessionsLoadingMore = ref(false)
const sessionsLoaded = ref(false)
const sessionsAllLoaded = ref(false)
const sessionsOffset = ref(0)
const SESSIONS_PAGE_SIZE = 20
const currentSessionId = ref<string | null>(null)
const historyScrollRef = ref<HTMLElement | null>(null)
const paginationSentinelRef = ref<HTMLElement | null>(null)
let paginationObserver: IntersectionObserver | null = null

// Session context menu state
const sessionMenu = ref<{
  visible: boolean
  session: SessionSummary | null
  x: number
  y: number
}>({ visible: false, session: null, x: 0, y: 0 })
const showRenameDialog = ref(false)
const renameInput = ref('')

// Group sessions by time bucket for display
const groupedSessions = computed(() => {
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart.getTime() - 86400000)
  const weekStart = new Date(todayStart.getTime() - 7 * 86400000)
  const monthStart = new Date(todayStart.getTime() - 30 * 86400000)

  const groups: Record<string, SessionSummary[]> = {}
  const order: string[] = []

  function addToGroup(label: string, session: SessionSummary) {
    if (!groups[label]) { groups[label] = []; order.push(label) }
    groups[label].push(session)
  }

  // Sessions already sorted by backend (pinned first, then updated_at desc)
  for (const s of sessions.value) {
    if (s.is_pinned) {
      addToGroup(t('aiChat.groupPinned'), s)
      continue
    }
    const d = new Date(s.updated_at)
    if (d >= todayStart) {
      addToGroup(t('aiChat.groupToday'), s)
    } else if (d >= yesterdayStart) {
      addToGroup(t('aiChat.groupYesterday'), s)
    } else if (d >= weekStart) {
      addToGroup(t('aiChat.groupWeek'), s)
    } else if (d >= monthStart) {
      addToGroup(t('aiChat.groupMonth'), s)
    } else {
      const label = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      addToGroup(label, s)
    }
  }

  return order.map((label) => ({ label, sessions: groups[label] }))
})

function openSessionMenu(session: SessionSummary, event: MouseEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const menuWidth = 140
  const x = Math.max(4, Math.min(rect.left - menuWidth, window.innerWidth - menuWidth - 4))
  sessionMenu.value = {
    visible: true,
    session,
    x,
    y: rect.bottom + 4,
  }
}

function closeSessionMenu() {
  sessionMenu.value.visible = false
}

function onRenameSession() {
  if (!sessionMenu.value.session) return
  renameInput.value = sessionMenu.value.session.title ?? ''
  showRenameDialog.value = true
  closeSessionMenu()
}

async function onConfirmRename() {
  const session = sessionMenu.value.session
  if (!session) return
  const title = renameInput.value.trim()
  if (!title) return
  try {
    await updateSession(session.session_id, { title })
    session.title = title
    showToast(t('aiChat.renameSessionSuccess'))
  } catch {
    showToast(t('aiChat.renameSessionFailed'))
  }
  showRenameDialog.value = false
}

async function onTogglePinSession() {
  const session = sessionMenu.value.session
  if (!session) return
  closeSessionMenu()
  const newPinned = !session.is_pinned
  try {
    await updateSession(session.session_id, { is_pinned: newPinned })
    session.is_pinned = newPinned
    // Re-sort: move pinned to front, unpinned back by updated_at
    sessions.value = [
      ...sessions.value.filter((s) => s.is_pinned),
      ...sessions.value.filter((s) => !s.is_pinned).sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      ),
    ]
    showToast(newPinned ? t('aiChat.pinSessionSuccess') : t('aiChat.unpinSessionSuccess'))
  } catch {
    // silently ignore
  }
}

async function onDeleteSession() {
  const session = sessionMenu.value.session
  if (!session) return
  closeSessionMenu()
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('aiChat.confirmDeleteSession') })
  } catch {
    return // cancelled
  }
  try {
    await deleteSessionApi(session.session_id)
    sessions.value = sessions.value.filter((s) => s.session_id !== session.session_id)
    showToast(t('aiChat.deleteSessionSuccess'))
    // If deleted session is the current one, reset to new chat
    if (currentSessionId.value === session.session_id) {
      messages.value = []
      currentSessionId.value = null
      customTitle.value = null
    }
  } catch {
    // silently ignore
  }
}

// Throttled markdown rendering state (scoped to this component instance)
let renderTimer: ReturnType<typeof setTimeout> | null = null
let pendingRenderText = ''
let pendingRenderTarget: { content: string; renderedContent: string } | null = null
let scrollRAF: number | null = null

// Follow global theme via data-theme attribute set by App.vue
const dataTheme = ref(document.documentElement.getAttribute('data-theme') ?? 'dark')
const isLight = computed(() => dataTheme.value === 'light')
let themeObserver: MutationObserver | null = null

let abortController: AbortController | null = null
let connectTimer: ReturnType<typeof setInterval> | null = null


const sessionTitle = computed(() => {
  const firstUser = messages.value.find((m) => m.role === 'user')
  if (!firstUser) return t('aiChat.newChat')
  const text = firstUser.content.trim()
  return text.length > 20 ? text.slice(0, 20) + '…' : text
})

// Typewriter effect for title
const displayedTitle = ref(t('aiChat.newChat'))
const customTitle = ref<string | null>(null)
const showEditTitleDialog = ref(false)
const editTitleInput = ref('')
let titleTimer: ReturnType<typeof setTimeout> | null = null

watch(sessionTitle, (newTitle) => {
  if (customTitle.value !== null) return // user has set a custom title, don't overwrite
  if (titleTimer) { clearTimeout(titleTimer); titleTimer = null }
  if (!newTitle || newTitle === t('aiChat.newChat')) {
    displayedTitle.value = newTitle
    return
  }
  // Animate character by character
  let i = 0
  displayedTitle.value = ''
  function tick() {
    if (i < newTitle.length) {
      displayedTitle.value = newTitle.slice(0, ++i)
      titleTimer = setTimeout(tick, 40)
    }
  }
  tick()
})

watch(customTitle, (val) => {
  if (val !== null) displayedTitle.value = val
})

function onEditTitle() {
  showEditTitleDialog.value = true
  editTitleInput.value = customTitle.value ?? sessionTitle.value
}

function onConfirmEditTitle() {
  const val = editTitleInput.value.trim()
  if (val) {
    customTitle.value = val.length > 30 ? val.slice(0, 30) + '…' : val
  }
  showEditTitleDialog.value = false
}

function onCancelEditTitle() {
  showEditTitleDialog.value = false
}

// Throttled markdown render helper (uses state declared above)
function renderMarkdownThrottled(text: string, target: { content: string; renderedContent: string }) {
  pendingRenderText = text
  pendingRenderTarget = target

  if (renderTimer) return // Already pending

  renderTimer = setTimeout(() => {
    renderTimer = null
    if (pendingRenderTarget && pendingRenderText) {
      pendingRenderTarget.renderedContent = renderMarkdown(pendingRenderText)
    }
  }, 100) // Render every 100ms max
}

async function scrollToBottom(force = false) {
  await nextTick()
  if (scrollRef.value) {
    if (!force && isUserScrolledUp.value) return // Don't auto-scroll when user has scrolled up
    if (scrollRAF) return // Already pending
    scrollRAF = requestAnimationFrame(() => {
      scrollRAF = null
      if (scrollRef.value) {
        scrollRef.value.scrollTop = scrollRef.value.scrollHeight
      }
    })
  }
}

function onChatScroll() {
  const el = scrollRef.value
  if (!el) return
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  // Mark as scrolled up when more than 100px from bottom (only during streaming)
  if (asking.value) {
    isUserScrolledUp.value = distFromBottom > 100
  }
}

function onScrollToBottom() {
  isUserScrolledUp.value = false
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

function onChipClick(text: string) {
  inputText.value = text
  onSend()
}

function phaseLabel(phase: NonNullable<Message['phase']>) {
  if (phase === 'connecting') return t('aiChat.connecting')
  if (phase === 'thinking') return t('aiChat.thinking')
  if (phase === 'answering') return t('aiChat.answering')
  return ''
}

// Load session list when history panel opens (lazy, once per mount)
const selectedCapability = ref<string>('chat')  // Default to 'chat' filter

// Capability metadata from skills/*.md - icons, colors, display names, and AI flag
const capabilityMeta: Record<string, { icon: string; color: string; name: string; isAI: boolean }> = {
  chat: { icon: '💬', color: '#06b6d4', name: '智能问答', isAI: true },
  alerts: { icon: '🔔', color: '#f59e0b', name: '资产老化预警', isAI: true },
  disposal: { icon: '🗑️', color: '#ef4444', name: '闲置资产处置', isAI: true },
  report: { icon: '📋', color: '#6366f1', name: '家庭资产体检', isAI: true },
  allocation: { icon: '📊', color: '#8b5cf6', name: '资产配置分析', isAI: true },
  liability: { icon: '💳', color: '#f97316', name: '负债健康分析', isAI: true },
  spending_leak: { icon: '💧', color: '#10b981', name: '消费漏洞扫描', isAI: true },
  time_machine: { icon: '⏰', color: '#a855f7', name: '财务时光机', isAI: false },  // simulation, not AI chat
}

const capabilityFilters = computed(() => [
  { label: t('aiChat.filterAll'), value: null },
  // Filter tabs for AI capabilities only (skip time_machine which doesn't generate chat history)
  ...Object.entries(capabilityMeta)
    .filter(([_, meta]) => meta.isAI)
    .map(([key, meta]) => ({
      label: `${meta.icon} ${meta.name}`,
      value: key,
    })),
])

async function loadSessions() {
  sessionsLoading.value = true
  sessionsOffset.value = 0
  sessionsAllLoaded.value = false
  try {
    // Pass capability filter - use null for "all" (when user explicitly selects filterAll)
    const capabilityParam = selectedCapability.value === 'all' ? undefined : selectedCapability.value
    const res = await getSessions(SESSIONS_PAGE_SIZE, 0, capabilityParam)
    sessions.value = res.data.sessions
    sessionsLoaded.value = true
    if (res.data.sessions.length < SESSIONS_PAGE_SIZE || sessions.value.length >= res.data.total) {
      sessionsAllLoaded.value = true
    }
    sessionsOffset.value = res.data.sessions.length
  } catch {
    // silently ignore — list stays empty
  } finally {
    sessionsLoading.value = false
  }
}

async function loadMoreSessions() {
  if (sessionsLoadingMore.value || sessionsAllLoaded.value || sessionsLoading.value) return
  sessionsLoadingMore.value = true
  // Capture the capability at call time; discard results if it changed mid-flight
  const capAtCall = selectedCapability.value
  try {
    const capabilityParam = capAtCall === 'all' ? undefined : capAtCall
    const res = await getSessions(SESSIONS_PAGE_SIZE, sessionsOffset.value, capabilityParam)
    if (selectedCapability.value !== capAtCall) return // stale response
    sessions.value = [...sessions.value, ...res.data.sessions]
    sessionsOffset.value += res.data.sessions.length
    if (res.data.sessions.length < SESSIONS_PAGE_SIZE || sessions.value.length >= res.data.total) {
      sessionsAllLoaded.value = true
    }
  } catch {
    // silently ignore
  } finally {
    sessionsLoadingMore.value = false
  }
}

async function onSelectCapability(cap: string | null) {
  // null means "全部" (all) - store as 'all' for consistency
  selectedCapability.value = cap ?? 'all'
  sessions.value = []
  sessionsOffset.value = 0
  sessionsAllLoaded.value = false
  sessionsLoaded.value = false
  await loadSessions()
}

watch(showHistory, async (open) => {
  if (!open || sessionsLoaded.value) return
  await loadSessions()
})

async function loadSessionMessages(session: SessionSummary) {
  showHistory.value = false
  messages.value = []
  currentSessionId.value = session.session_id
  asking.value = true
  connecting.value = true
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  try {
    reader = await streamSessionEvents(session.session_id)
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let nl = buf.indexOf('\n')
      while (nl >= 0) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line) { nl = buf.indexOf('\n'); continue }
        try {
          const event = JSON.parse(line)
          if (event.type === 'user.message') {
            messages.value.push({
              id: event.eventId ?? Date.now().toString(),
              role: 'user',
              content: event.content ?? '',
              created_at: event.timestamp ?? new Date().toISOString(),
              displayTime: formatTime(event.timestamp ?? new Date().toISOString()),
            })
          } else if (event.type === 'assistant.message') {
            messages.value.push({
              id: event.eventId ?? Date.now().toString(),
              role: 'assistant',
              phase: 'done',
              content: event.content ?? '',
              renderedContent: renderMarkdown(event.content ?? ''),
              created_at: event.timestamp ?? new Date().toISOString(),
              displayTime: formatTime(event.timestamp ?? new Date().toISOString()),
            })
          }
        } catch { /* skip malformed */ }
        nl = buf.indexOf('\n')
      }
    }
  } catch {
    showToast(t('aiChat.loadSessionFailed'))
  } finally {
    reader?.cancel().catch(() => {})
    asking.value = false
    connecting.value = false
    await scrollToBottom()
  }
}

async function onNewChat() {
  if (messages.value.length === 0) return
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('aiChat.newChatConfirm') })
    messages.value = []
    currentSessionId.value = null
    customTitle.value = null
    sessionsLoaded.value = false  // force refresh next time history panel opens
    sessions.value = []
    sessionsOffset.value = 0
    sessionsAllLoaded.value = false
  } catch {
    // cancelled
  }
}

async function onSend() {
  const q = inputText.value.trim()
  if (!q || asking.value) return

  const userMsgId = Date.now().toString()
  messages.value.push({
    id: userMsgId,
    role: 'user',
    sendStatus: 'sending',
    content: q,
    created_at: new Date().toISOString(),
    displayTime: formatTime(new Date().toISOString()),
  })
  inputText.value = ''
  asking.value = true
  connecting.value = true  // Show connecting animation first
  connectingSeconds.value = 0
  connectTimer = setInterval(() => { connectingSeconds.value++ }, 1000)
  abortController = new AbortController()
  await scrollToBottom()
  const userMsgIdx = messages.value.findIndex((m) => m.id === userMsgId)

  // Add assistant message placeholder (with think block if deep_think)
  const thinkStart = deepThink.value ? Date.now() : 0
  const assistantMsg: Message = {
    id: `pending-${Date.now()}`,
    role: 'assistant',
    phase: 'connecting',
    content: '',
    renderedContent: '',
    created_at: new Date().toISOString(),
    displayTime: formatTime(new Date().toISOString()),
    thinkContent: deepThink.value ? '' : undefined,
    thinkOpen: deepThink.value ? true : undefined,
    thinkDone: deepThink.value ? false : undefined,
    thinkSeconds: deepThink.value ? 0 : undefined,
    toolTimeline: [],
  }
  messages.value.push(assistantMsg)
  const msgIdx = messages.value.length - 1
  await scrollToBottom()

  let thinkTimer: ReturnType<typeof setInterval> | null = null
  if (deepThink.value) {
    thinkTimer = setInterval(() => {
      if (!messages.value[msgIdx].thinkDone) {
        messages.value[msgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
      }
    }, 1000)
  }

  const decoder = new TextDecoder()
  let thinkRaw = ''
  let textRaw = ''
  let thinkingDone = false

  try {
    const reader = await sendChatEventStream(q, deepThink.value, webSearch.value, abortController.signal, currentSessionId.value ?? undefined)
    const parser = createAgentEventParser(handleEvent)

    // Connection established, hide connecting animation
    if (connectTimer) { clearInterval(connectTimer); connectTimer = null }
    connecting.value = false
    messages.value[msgIdx].phase = deepThink.value ? 'thinking' : 'answering'
    // Mark user message as sent
    if (userMsgIdx >= 0) {
      messages.value[userMsgIdx].sendStatus = 'sent'
    }
    await scrollToBottom()

    function handleEvent(event: AgentEvent) {
      if (event.type === 'session.start') {
        if (event.session_id) currentSessionId.value = event.session_id
        return
      }
      if (event.type === 'phase.connecting') {
        messages.value[msgIdx].phase = 'connecting'
        return
      }
      if (event.type === 'phase.thinking') {
        messages.value[msgIdx].phase = 'thinking'
        return
      }
      if (event.type === 'phase.answering') {
        messages.value[msgIdx].phase = 'answering'
        // Auto-collapse think block when answering starts, unless user manually toggled it
        if (messages.value[msgIdx].thinkDone && !messages.value[msgIdx].thinkManuallyToggled) {
          messages.value[msgIdx].thinkOpen = false
        }
        return
      }
      if (event.type === 'token.stream' && event.is_thinking) {
        thinkRaw += event.token ?? ''
        messages.value[msgIdx].thinkContent = renderMarkdown(thinkRaw)
        return
      }
      if (event.type === 'token.stream') {
        if (!thinkingDone && deepThink.value) {
          thinkingDone = true
          if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
          messages.value[msgIdx].thinkDone = true
          messages.value[msgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
          // Auto-collapse unless user manually toggled
          if (!messages.value[msgIdx].thinkManuallyToggled) {
            messages.value[msgIdx].thinkOpen = false
          }
          // Final render for think content
          if (thinkRaw) {
            messages.value[msgIdx].thinkContent = renderMarkdown(thinkRaw)
          }
        }
        textRaw += event.token ?? ''
        messages.value[msgIdx].content = textRaw
        // Use throttled rendering for smoother streaming
        renderMarkdownThrottled(textRaw, messages.value[msgIdx])
        scrollToBottom()
        return
      }
      if (event.type === 'tool.call' && event.tool) {
        messages.value[msgIdx].toolTimeline ??= []
        messages.value[msgIdx].toolTimeline.push({
          id: event.tool.id,
          name: event.tool.name,
          displayName: event.tool.display_name,
          icon: event.tool.icon,
          argumentsText: formatToolArguments(event.tool.arguments),
        })
        return
      }
      if (event.type === 'tool.result' && event.tool_id) {
        messages.value[msgIdx].toolTimeline ??= []
        const tool = messages.value[msgIdx].toolTimeline.find((item) => item.id === event.tool_id)
        const result = event.result
          ? {
              success: event.result.success,
              summary: event.result.summary,
              data: event.result.data,
              error: event.result.error,
              execution_time_ms: event.result.execution_time_ms,
            }
          : undefined
        if (tool) {
          tool.result = result
        } else {
          messages.value[msgIdx].toolTimeline.push({
            id: event.tool_id,
            name: event.tool_id,
            displayName: event.tool_id,
            icon: 'tool',
            argumentsText: '',
            result,
          })
        }
        return
      }
      if (event.type === 'capability.error') {
        messages.value[msgIdx].phase = 'error'
        messages.value[msgIdx].content = event.error?.message ?? t('toast.aiChatError')
        messages.value[msgIdx].renderedContent = renderMarkdown(messages.value[msgIdx].content)
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      parser.push(decoder.decode(value, { stream: true }))
    }
    parser.flush()

    // Flush pending markdown render
    if (renderTimer) {
      clearTimeout(renderTimer)
      renderTimer = null
      if (pendingRenderTarget && pendingRenderText) {
        pendingRenderTarget.renderedContent = renderMarkdown(pendingRenderText)
      }
    }

    // Finalize think block if no text came (e.g. error from agent)
    if (deepThink.value && !thinkingDone) {
      if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
      messages.value[msgIdx].thinkDone = true
      if (!messages.value[msgIdx].thinkManuallyToggled) {
        messages.value[msgIdx].thinkOpen = false
      }
      messages.value[msgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
      // Final render for think content
      if (thinkRaw) {
        messages.value[msgIdx].thinkContent = renderMarkdown(thinkRaw)
      }
    }

    messages.value[msgIdx].phase = textRaw ? 'done' : 'error'
    asking.value = false
    connecting.value = false
    isUserScrolledUp.value = false
    abortController = null
    await scrollToBottom(true)
  } catch (err: unknown) {
    if (thinkTimer) clearInterval(thinkTimer)
    if (connectTimer) { clearInterval(connectTimer); connectTimer = null }
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'CanceledError')) {
      // Finalize the assistant message so it doesn't stay in connecting/thinking/answering phase
      if (messages.value[msgIdx]) {
        messages.value[msgIdx].phase = textRaw ? 'interrupted' : 'error'
        if (!textRaw) {
          messages.value[msgIdx].content = t('toast.aiChatError')
          messages.value[msgIdx].renderedContent = `<p>${t('toast.aiChatError')}</p>`
        }
      }
      asking.value = false
      connecting.value = false
      isUserScrolledUp.value = false
      abortController = null
      return
    }
    // Mark user message as failed so the retry indicator shows
    if (userMsgIdx >= 0) {
      messages.value[userMsgIdx].sendStatus = 'failed'
    }
    messages.value[msgIdx] = {
      id: Date.now().toString(),
      role: 'assistant',
      phase: 'error',
      content: t('toast.aiChatError'),
      renderedContent: `<p>${t('toast.aiChatError')}</p>`,
      created_at: new Date().toISOString(),
      displayTime: formatTime(new Date().toISOString()),
    }
    asking.value = false
    connecting.value = false
    abortController = null
    await scrollToBottom()
  }
}

function formatToolArguments(args: Record<string, unknown>) {
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(' · ')
}

function toolIcon(icon: string) {
  const map: Record<string, string> = {
    search: '⌕',
    tool: '◇',
  }
  return map[icon] ?? '◇'
}

function toolStatus(tool: ToolTimelineItem) {
  if (!tool.result) return t('aiChat.toolRunning')
  if (tool.result.success === false) return t('aiChat.toolFailed')
  return t('aiChat.toolDone')
}

function toolResultText(result: NonNullable<ToolTimelineItem['result']>) {
  if (result.error) return result.error
  if (result.summary) return result.summary
  if (typeof result.data === 'string') return result.data
  if (result.data !== undefined && result.data !== null) return JSON.stringify(result.data)
  return t('aiChat.toolDone')
}

function onAbort() {
  abortController?.abort()
  if (connectTimer) { clearInterval(connectTimer); connectTimer = null }
  // Mark the last in-progress assistant message as interrupted
  const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant' && m.phase === 'answering')
  if (lastAssistant) lastAssistant.phase = 'interrupted'
  asking.value = false
  connecting.value = false
  abortController = null
}

function onThinkToggle(msg: Message) {
  msg.thinkManuallyToggled = true
  msg.thinkOpen = !msg.thinkOpen
}

async function onAction(type: 'file' | 'image' | 'link' | 'clear' | 'camera' | 'ocr' | 'webpage' | 'history') {
  if (type === 'clear') {
    try {
      await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmClearChat') })
      await clearChatHistory()
      messages.value = []
    } catch {
      // cancelled
    }
    return
  }
  showToast(t('toast.featureComingSoon'))
}

async function onCopy(content: string) {
  // Try modern Clipboard API first
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(content)
      showToast(t('toast.copied'))
      return
    } catch {
      // Fall through to legacy method
    }
  }
  // Fallback: use textarea + execCommand for older browsers / insecure contexts
  try {
    const textarea = document.createElement('textarea')
    textarea.value = content
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const success = document.execCommand('copy')
    document.body.removeChild(textarea)
    if (success) {
      showToast(t('toast.copied'))
    } else {
      showToast(t('toast.copyFailed'))
    }
  } catch {
    showToast(t('toast.copyFailed'))
  }
}

function onEditUserMessage(idx: number) {
  const msg = messages.value[idx]
  if (!msg || msg.role !== 'user') return
  // Remove all messages from this user message onwards
  messages.value.splice(idx)
  // Put the content back into input for editing
  inputText.value = msg.content
}

async function onRegenerate(idx: number) {
  const prevUser = [...messages.value].slice(0, idx).reverse().find((m) => m.role === 'user')
  if (!prevUser || asking.value) return

  const prevUserIdx = messages.value.indexOf(prevUser)
  // Remove the assistant response and the preceding user message, then re-send
  // This avoids duplicating the user message when onSend() pushes a new one
  messages.value.splice(prevUserIdx, idx - prevUserIdx + 1)
  inputText.value = prevUser.content
  await onSend()
}

function onFeedback(id: string, value: 1 | -1) {
  const msg = messages.value.find((m) => m.id === id)
  if (!msg) return
  msg.feedback = msg.feedback === value ? 0 : value
}

async function onRetryError(idx: number) {
  if (asking.value) return
  // Find the preceding user message
  const prevUser = [...messages.value].slice(0, idx).reverse().find((m) => m.role === 'user')
  if (!prevUser) return
  // Remove the error assistant message
  messages.value.splice(idx, 1)
  // Re-send the user's question
  inputText.value = prevUser.content
  await onSend()
}

async function onRetrySend(idx: number) {
  if (asking.value) return
  const msg = messages.value[idx]
  if (!msg || msg.role !== 'user') return
  // Reset send status and re-send
  msg.sendStatus = 'sending'
  inputText.value = msg.content
  // Remove this user message so onSend re-pushes it fresh
  messages.value.splice(idx, 1)
  await onSend()
}

// Infinite scroll: watch sentinel at setup level so the watcher is properly tracked
// and cleaned up by Vue's effect scope (not leaked inside onMounted)
watch(paginationSentinelRef, (el) => {
  paginationObserver?.disconnect()
  if (el) paginationObserver?.observe(el)
})

onMounted(async () => {
  // Observe data-theme attribute changes on <html> to stay in sync with global theme
  themeObserver = new MutationObserver(() => {
    dataTheme.value = document.documentElement.getAttribute('data-theme') ?? 'dark'
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

  // Bind scroll listener for auto-scroll pause detection
  scrollRef.value?.addEventListener('scroll', onChatScroll, { passive: true })

  // Create IntersectionObserver for infinite scroll
  paginationObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) loadMoreSessions()
    },
    { threshold: 0.1 },
  )
  // Observe sentinel if it's already in the DOM (e.g. history panel open on mount)
  if (paginationSentinelRef.value) paginationObserver.observe(paginationSentinelRef.value)

  // Default deep think on if the primary model has passed the thinking capability test
  // or if it was enabled from AIHubPage
  if (!aiStore.config) await aiStore.fetchConfig()
  const routeDeepThink = route.query.deepThink === '1'
  const routeWebSearch = route.query.webSearch === '1'
  const isNewSession = route.query.newSession === '1'

  if (routeDeepThink || aiStore.deepThinkEnabled || aiStore.config?.ai_test_thinking_success === true) {
    deepThink.value = true
    aiStore.deepThinkEnabled = false // Reset after using
  }
  if (routeWebSearch || aiStore.webSearchEnabled) {
    webSearch.value = true
    aiStore.webSearchEnabled = false
  }

  // Start fresh session when navigating from hub with newSession flag
  if (isNewSession) {
    messages.value = []
  } else {
    // Load existing history (normal navigation)
    try {
      const res = await getChatHistory()
      if (res.data.session_id) {
        currentSessionId.value = res.data.session_id
      }
      messages.value = res.data.messages.map((m) => ({
        ...m,
        displayTime: formatTime(m.created_at),
        renderedContent: m.role === 'assistant' ? renderMarkdown(m.content) : undefined,
      }))
      await markChatRead()
      await scrollToBottom()
    } catch {
      // no history
    }
  }

  // Send user's question from hub or route query
  const q = aiStore.draftQuery || route.query.q
  if (typeof q === 'string' && q.trim()) {
    inputText.value = q.trim()
    aiStore.draftQuery = ''
    await onSend()
  }
})

onUnmounted(() => {
  themeObserver?.disconnect()
  paginationObserver?.disconnect()
  scrollRef.value?.removeEventListener('scroll', onChatScroll)
})
</script>

<style scoped>
/* ── CSS variables for day/night theme ── */
.ai-chat-page {
  --bg: #0f1117;
  --bg-header: rgba(15, 17, 23, 0.95);
  --border: rgba(255, 255, 255, 0.06);
  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.5);
  --text-muted: rgba(255, 255, 255, 0.3);
  --bubble-user-bg: rgba(99, 102, 241, 0.22);
  --bubble-user-color: #ffffff;
  --bubble-ai-bg: rgba(189, 187, 255, 0.12);
  --bubble-ai-color: rgba(255, 255, 255, 0.85);
  --bubble-ai-border: rgba(189, 187, 255, 0.2);
  --btn-color: rgba(255, 255, 255, 0.7);
  --btn-hover-bg: rgba(255, 255, 255, 0.08);
  --suggestion-bg: rgba(255, 255, 255, 0.08);
  --suggestion-border: rgba(255, 255, 255, 0.12);
  --think-bg: rgba(99, 102, 241, 0.08);
  --think-border: rgba(99, 102, 241, 0.25);
  --think-color: rgba(255, 255, 255, 0.55);
  --shimmer-color: rgba(255, 255, 255, 0.06);
}

.ai-chat-page.theme-light {
  --bg: #f5f5f7;
  --bg-header: rgba(245, 245, 247, 0.95);
  --border: rgba(0, 0, 0, 0.25);
  --text-primary: rgba(0, 0, 0, 0.9);
  --text-secondary: rgba(0, 0, 0, 0.6);
  --text-muted: rgba(0, 0, 0, 0.45);
  --bubble-user-bg: #e8e8f4;
  --bubble-user-color: #1a1a2e;
  --bubble-ai-bg: rgba(189, 187, 255, 0.22);
  --bubble-ai-color: rgba(0, 0, 0, 0.9);
  --bubble-ai-border: rgba(0, 0, 0, 0.15);
  --btn-color: rgba(0, 0, 0, 0.7);
  --btn-hover-bg: rgba(0, 0, 0, 0.1);
  --suggestion-bg: #fff;
  --suggestion-border: rgba(0, 0, 0, 0.2);
  --think-bg: rgba(99, 102, 241, 0.1);
  --think-border: rgba(99, 102, 241, 0.35);
  --think-color: rgba(0, 0, 0, 0.7);
  --shimmer-color: rgba(255, 255, 255, 0.45);
}

/* ── Page shell ── */
.ai-chat-page {
  display: flex;
  flex-direction: column;
  position: fixed;
  inset: 0;
  bottom: calc(50px + env(safe-area-inset-bottom));
  background: var(--bg);
  z-index: 10;
}

/* ── Header ── */
.chat-header {
  display: flex;
  align-items: center;
  padding: 0 4px;
  padding-top: env(safe-area-inset-top);
  height: calc(50px + env(safe-area-inset-top));
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.header-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--btn-color);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.header-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--text-primary);
}

.header-title-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 0;
  padding: 0 4px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-edit-btn {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.header-edit-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
}

/* ── History sidebar ── */
.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  padding: env(safe-area-inset-top) 0 0;
}

.history-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.history-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.history-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
}

.filter-tab {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.filter-tab--active {
  background: var(--text-primary);
  color: var(--bg);
  border-color: var(--text-primary);
}

.history-empty {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 14px;
}

.history-empty p {
  margin: 0;
}

.history-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

.history-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0 16px;
}

.history-group-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 10px 16px 4px;
}

.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 8px 8px 16px;
  cursor: pointer;
  border-radius: 0;
  transition: background 0.12s;
  position: relative;
}

.history-item:hover {
  background: var(--btn-hover-bg);
}

.history-item--active {
  background: rgba(99, 102, 241, 0.15);
}

.history-item--active:hover {
  background: rgba(99, 102, 241, 0.2);
}

.history-item-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.history-item-menu-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px;
  opacity: 0;
  transition: opacity 0.12s, background 0.12s, color 0.12s;
}

.history-item:hover .history-item-menu-btn,
.history-item--active .history-item-menu-btn {
  opacity: 1;
}

.history-item-menu-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--text-primary);
}

/* ── Session context menu ── */
.session-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
}

.session-menu {
  position: fixed;
  z-index: 101;
  background: var(--bg-header);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(1, 1, 32, 0.2);
  min-width: 140px;
  overflow: hidden;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.session-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s;
}

.session-menu-item:hover {
  background: var(--btn-hover-bg);
}

.session-menu-item--danger {
  color: #f87171;
}

.session-menu-item--danger:hover {
  background: rgba(248, 113, 113, 0.1);
}

/* ── Chat body ── */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overscroll-behavior: contain;
}

/* Desktop centering */
@media (min-width: 640px) {
  .chat-body {
    padding: 16px calc(50% - 384px + 16px) 8px;
  }
  .input-bar {
    padding: 8px calc(50% - 384px + 16px) calc(12px + env(safe-area-inset-bottom));
  }
}

/* ── Empty state ── */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 0 16px;
  gap: 8px;
}

.empty-hero {
  position: relative;
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}

.hero-glow {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.4) 0%, transparent 70%);
  animation: pulse-glow 3s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}

.hero-icon {
  width: 48px;
  height: 48px;
  color: #818cf8;
  position: relative;
  z-index: 1;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px;
}

/* ── Suggestion cards ── */
.suggestion-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.suggestion-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--suggestion-bg);
  border: 1px solid var(--suggestion-border);
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s, transform 0.15s;
  width: 100%;
}

.suggestion-card:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
}

.suggestion-card:active {
  transform: scale(0.98);
}

.suggestion-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  flex-shrink: 0;
}

.suggestion-text {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.4;
}

.suggestion-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
}

/* ── Messages ── */
.message-row {
  display: flex;
  flex-direction: column;
}

.message-row.user { align-items: flex-end; }
.message-row.assistant { align-items: flex-start; }

.bubble {
  max-width: 86%;
}

.bubble-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.message-row.user .bubble-body {
  align-items: flex-end;
}

/* ── Assistant phase strip ── */
.phase-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  max-width: 100%;
  padding: 8px 12px;
  background: rgba(189, 187, 255, 0.1);
  border: 1px solid var(--bubble-ai-border);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.2;
  box-shadow: rgba(1, 1, 32, 0.08) 0 4px 10px;
}

.phase-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #818cf8;
  box-shadow: 0 0 0 0 rgba(129, 140, 248, 0.5);
  animation: phase-pulse 1.4s ease-out infinite;
  flex-shrink: 0;
}

.phase-strip--answering .phase-pulse {
  background: #6ee7a0;
  box-shadow: 0 0 0 0 rgba(110, 231, 160, 0.45);
}

/* Standalone phase strip (non-deep-think mode) */
.phase-strip.standalone {
  justify-content: center;
  margin-bottom: 4px;
}

/* Small pulse for think block icon wrapper */
.phase-pulse-small {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #818cf8;
  box-shadow: 0 0 0 0 rgba(129, 140, 248, 0.5);
  animation: phase-pulse 1.4s ease-out infinite;
}

.phase-label {
  color: var(--text-primary);
  font-weight: 500;
}

.phase-meta {
  color: var(--text-secondary);
  font-family: 'Georgia', monospace;
}

@keyframes phase-pulse {
  0% { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
  70% { box-shadow: 0 0 0 7px transparent; opacity: 0.7; }
  100% { box-shadow: 0 0 0 0 transparent; opacity: 1; }
}

/* ── Deep think block ── */
.think-block {
  background: var(--think-bg);
  border: 1px solid var(--think-border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 4px;
}

.think-block--active {
  border-color: rgba(99, 102, 241, 0.3);
  background: rgba(99, 102, 241, 0.12);
}

.think-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  color: #818cf8;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  position: relative;
}

.think-toggle:hover {
  background: rgba(99, 102, 241, 0.08);
}

.think-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.15);
  flex-shrink: 0;
}

.think-block:not(.think-block--done) .think-icon-wrapper {
  animation: pulse-icon 2s ease-in-out infinite;
}

@keyframes pulse-icon {
  0%, 100% { background: rgba(99, 102, 241, 0.15); }
  50% { background: rgba(99, 102, 241, 0.25); }
}

.think-status {
  font-weight: 500;
  position: relative;
}

.think-status--active {
  overflow: hidden;
  position: relative;
}

.think-text-animated {
  display: inline-block;
  position: relative;
  background: linear-gradient(
    90deg,
    rgba(129, 140, 248, 0.7) 0%,
    #818cf8 50%,
    rgba(129, 140, 248, 0.7) 100%
  );
  background-size: 200% 100%;
  animation: shimmer-text 2s linear infinite;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

@keyframes shimmer-text {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.think-duration {
  font-size: 11px;
  color: rgba(129, 140, 248, 0.7);
  background: rgba(99, 102, 241, 0.12);
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 2px;
}

.think-chip-sep {
  color: var(--text-muted);
  font-size: 11px;
  margin: 0 2px;
}

.think-chip {
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(99, 102, 241, 0.08);
  padding: 1px 5px;
  border-radius: 4px;
}

.tool-result--failed {
  color: #f87171;
  font-size: 11px;
  padding: 4px 0 0;
}

.think-chevron {
  margin-left: auto;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.think-block--open .think-chevron {
  transform: rotate(180deg);
}

.think-content {
  padding: 8px 12px 10px;
  font-size: 12px;
  color: var(--think-color);
  line-height: 1.6;
  border-top: 1px solid var(--think-border);
}

.think-content :deep(p) { margin: 0 0 4px; }
.think-content :deep(p:last-child) { margin-bottom: 0; }

/* ── Tool timeline ── */
.tool-timeline {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: min(100%, 320px);
  margin-bottom: 4px;
}

.tool-card {
  border: 1px solid var(--bubble-ai-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  padding: 9px 10px;
  box-shadow: rgba(1, 1, 32, 0.08) 0 4px 10px;
}

.tool-card--done {
  border-color: rgba(110, 231, 160, 0.28);
}

.tool-card--error {
  border-color: rgba(248, 113, 113, 0.34);
}

.tool-card-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: rgba(189, 187, 255, 0.12);
  color: var(--text-primary);
  font-size: 14px;
  flex-shrink: 0;
}

.tool-card-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.tool-card-title {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
}

.tool-card-meta,
.tool-card-args,
.tool-result {
  font-size: 11px;
  line-height: 1.35;
}

.tool-card-args {
  margin-top: 7px;
  color: var(--text-muted);
  overflow-wrap: anywhere;
}

.tool-result {
  margin-top: 7px;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.bubble-text {
  display: block;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

/* Markdown content inside assistant bubbles */
.bubble.assistant .bubble-text :deep(p) { margin: 0 0 8px; }
.bubble.assistant .bubble-text :deep(p:last-child) { margin-bottom: 0; }
.bubble.assistant .bubble-text :deep(ul),
.bubble.assistant .bubble-text :deep(ol) { margin: 4px 0 8px 16px; padding: 0; }
.bubble.assistant .bubble-text :deep(li) { margin-bottom: 2px; }
.bubble.assistant .bubble-text :deep(code) {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.bubble.assistant .bubble-text :deep(pre) {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--bubble-ai-border);
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.bubble.assistant .bubble-text :deep(pre code) {
  background: transparent;
  padding: 0;
  color: var(--bubble-ai-color);
}
.bubble.assistant .bubble-text :deep(strong) { color: var(--text-primary); }
.bubble.assistant .bubble-text :deep(a) { color: #818cf8; text-decoration: underline; word-break: break-all; }
/* Mobile overflow fixes for code blocks and tables */
.bubble.assistant .bubble-text :deep(pre) { max-width: 100%; -webkit-overflow-scrolling: touch; }
.bubble.assistant .bubble-text :deep(table) {
  display: block;
  overflow-x: auto;
  max-width: 100%;
  -webkit-overflow-scrolling: touch;
  border-collapse: collapse;
  font-size: 13px;
}
.bubble.assistant .bubble-text :deep(th),
.bubble.assistant .bubble-text :deep(td) {
  border: 1px solid var(--bubble-ai-border);
  padding: 4px 8px;
  white-space: nowrap;
}
.bubble.assistant .bubble-text :deep(img) { max-width: 100%; height: auto; }

/* ── Streaming cursor ── */
.stream-cursor {
  display: inline-block;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1;
  margin-left: 1px;
  animation: cursor-blink 0.8s step-end infinite;
}
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .stream-cursor { animation: none; }
}

/* ── Interrupted hint ── */
.interrupted-hint {
  font-size: 12px;
  color: var(--text-muted);
  padding: 4px 4px 0;
}

.bubble.user .bubble-text {
  background: var(--bubble-user-bg);
  color: var(--bubble-user-color);
  border-bottom-right-radius: 4px;
}

.bubble.assistant .bubble-text {
  background: var(--bubble-ai-bg);
  color: var(--bubble-ai-color);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--bubble-ai-border);
}

.msg-time {
  font-size: 11px;
  color: var(--text-muted);
  padding: 0 4px;
}

/* ── User message send status ── */
.send-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 2px 4px;
  justify-content: flex-end;
}
.send-status--sending {
  color: var(--text-muted);
}
.send-status--failed {
  color: #f87171;
}
.send-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: send-dot-pulse 1.2s ease-in-out infinite;
}
@keyframes send-dot-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}
@media (prefers-reduced-motion: reduce) {
  .send-status-dot { animation: none; opacity: 0.7; }
}
.send-retry-btn {
  background: none;
  border: 1px solid currentColor;
  border-radius: 4px;
  color: inherit;
  cursor: pointer;
  font-size: 11px;
  padding: 1px 6px;
  min-height: 22px;
}
.send-retry-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Message action buttons ── */
.msg-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

/* User message actions - positioned on right */
.msg-actions--user {
  justify-content: flex-end;
}

.message-row:hover .msg-actions,
.message-row:focus-within .msg-actions,
.message-row:active .msg-actions {
  opacity: 1;
}

/* Mobile: always show actions for touch */
@media (max-width: 768px) {
  .msg-actions {
    opacity: 1;
  }
}

/* List reorder animation */
.msg-move {
  transition: transform 0.2s ease;
}

.msg-action-btn {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.msg-action-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--btn-color);
}

.msg-action-btn:disabled {
  cursor: default;
  opacity: 0.3;
}

.msg-action-btn--active {
  color: #818cf8;
}

/* ── Message enter animation ── */
.msg-list {
  display: contents;
}

.msg-enter-active {
  animation: msg-in 0.2s ease-out both;
}

@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Scroll-to-bottom floating button ── */
.scroll-to-bottom-btn {
  position: fixed;
  bottom: calc(72px + env(safe-area-inset-bottom));
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  background: var(--suggestion-bg);
  border: 1px solid var(--suggestion-border);
  border-radius: 20px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  z-index: 10;
  white-space: nowrap;
  min-height: 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.scroll-to-bottom-btn:active {
  opacity: 0.8;
}
.scroll-btn-enter-active,
.scroll-btn-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.scroll-btn-enter-from,
.scroll-btn-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

/* ── Input bar ── */
.input-bar {
  padding: 8px 16px calc(12px + env(safe-area-inset-bottom));
  background: var(--bg-header);
  border-top: 1px solid var(--border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

@media (prefers-reduced-motion: reduce) {
  .hero-glow,
  .suggestion-card,
  .msg-enter-active,
  .phase-pulse,
  .think-icon-wrapper,
  .think-text-animated,
  .thinking-halo,
  .bubble-text--appearing {
    animation: none;
    transition: none;
  }
}

/* ── Thinking halo effect ── */
.bubble.assistant--thinking {
  position: relative;
  overflow: visible;
}

/* ── Connecting state region ── */
.connecting-region {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 4px;
  font-size: 13px;
  color: var(--text-secondary);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}
.connecting-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-secondary);
  flex-shrink: 0;
  animation: connecting-pulse 1.2s ease-in-out infinite;
}
@keyframes connecting-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.15); }
}
.connecting-label { font-size: 13px; }
.connecting-sep { color: var(--text-muted); }
.connecting-time { color: var(--text-muted); font-size: 12px; font-variant-numeric: tabular-nums; }

/* ── Shimmer sweep animation ── */
.shimmer-active {
  background-image: linear-gradient(
    90deg,
    transparent 0%,
    var(--shimmer-color, rgba(255,255,255,0.07)) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer-sweep 2s linear infinite;
}
@keyframes shimmer-sweep {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .shimmer-active { animation: none; background-image: none; }
  .connecting-dot { animation: none; opacity: 0.7; }
}

.thinking-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 20px;
  min-height: 48px;
}

.thinking-halo {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    rgba(189, 187, 255, 0.2),
    rgba(129, 140, 248, 0.6),
    rgba(189, 187, 255, 0.2),
    rgba(129, 140, 248, 0.6),
    rgba(189, 187, 255, 0.2)
  );
  animation: halo-spin 1.5s linear infinite;
  position: relative;
}

.thinking-halo::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 50%;
  background: var(--bg);
}

@keyframes halo-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.thinking-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

/* ── Bubble content fade-in ── */
.bubble-text--appearing {
  animation: content-fade-in 0.2s ease-out;
}

@keyframes content-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ── Error state ── */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
}

.error-msg {
  font-size: 13px;
  color: #f87171;
  margin: 0;
  line-height: 1.5;
}

.error-retry-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 8px;
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.error-retry-btn:hover {
  background: rgba(248, 113, 113, 0.18);
  border-color: rgba(248, 113, 113, 0.45);
}

.error-retry-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

/* Light mode error adjustments */
.ai-chat-page.theme-light .error-retry-btn {
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.12);
}

.ai-chat-page.theme-light .error-retry-btn:hover {
  background: rgba(248, 113, 113, 0.22);
}

/* ── History pagination sentinel ── */
.history-pagination-sentinel {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.history-load-more-text {
  font-size: 11px;
  color: var(--text-muted);
}
</style>
