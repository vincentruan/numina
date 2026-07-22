<template>
  <div class="baby-page">
    <PageHeader :title="t('baby.title')" :show-back="false" />

    <!-- Skeleton for initial loading -->
    <BabyPageSkeleton v-if="loading && childMembers.length === 0" />

    <!-- Actual Content -->
    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- No Children State -->
      <EmptyState v-if="childMembers.length === 0" :description="t('baby.noChildren')">
        <van-button type="primary" size="small" @click="$router.push('/family/members')">
          {{ t('baby.addChildren') }}
        </van-button>
      </EmptyState>

      <!-- Child Selector + Content -->
      <template v-else>
        <!-- Child Tabs -->
        <van-tabs v-model:active="activeChildIndex" scrollable class="child-tabs">
          <van-tab :title="t('baby.tabAll')" />
          <van-tab v-for="child in childMembers" :key="child.id">
            <template #title>
              <div class="child-tab-title">
                <div class="child-tab-avatar" :style="{ background: child.avatar_color || '#FF6B6B' }">
                  {{ (child.display_name ?? '?').charAt(0) }}
                </div>
                <span class="child-tab-name">{{ child.display_name }}</span>
              </div>
            </template>
          </van-tab>
        </van-tabs>

        <!-- Pending Approvals (filtered by selected child) -->
        <PendingApprovalsSection
          v-if="authStore.user?.role === 'owner'"
          :child-id="selectedChildId ? String(selectedChildId) : null"
        />

        <!-- Summary Card -->
        <van-cell-group inset class="summary-card">
          <van-cell :title="t('baby.balance')">
            <template #value>
              <div class="balance-row">
                <span>{{ currentBalance }} ⭐</span>
                <van-button
                  size="mini"
                  type="warning"
                  plain
                  class="grant-btn"
                  @click="openGrantSheet"
                >{{ t('baby.grantBtn') }}</van-button>
              </div>
            </template>
          </van-cell>
          <van-cell :title="t('baby.weeklyChores')" :value="`${currentChoreStats.completed_this_week ?? 0}/${currentChoreStats.total_this_week ?? 0}`" />
          <van-cell :title="t('baby.activeWishes')" :value="`${currentWishCount}`" />
          <van-cell :title="t('baby.blindBoxGifts')" is-link @click="$router.push('/blind-box/gifts')" />
          <van-cell :title="t('baby.blindBoxDraws')" is-link @click="$router.push('/blind-box/draws')">
            <template v-if="pendingDrawCount > 0" #value>
              <van-badge :content="pendingDrawCount" />
            </template>
          </van-cell>
          <van-cell :title="t('baby.choreTemplates')" is-link @click="$router.push('/baby/chore-templates')" />
        </van-cell-group>

        <!-- Content Tabs -->
        <van-tabs v-model:active="activeContentTab" class="content-tabs">
          <van-tab :title="t('baby.tabDiary')">
            <van-cell-group inset>
              <van-cell :title="t('baby.weeklyRate')" :value="`${weeklyCompletionRate}%`" />
            </van-cell-group>
            <div class="calendar-wrap">
              <ChildCalendar
                v-if="calendarChildId"
                :key="calendarChildId"
                :fetch-month="fetchCalendarMonth"
                day-route="/baby/calendar/day"
                :extra-query="{ child_id: calendarChildId }"
                :display-hint="calendarDisplayHint"
                variant="parent"
                :show-completion-rate="true"
              />
            </div>
          </van-tab>

          <van-tab :title="t('baby.tabWishes')">
            <div class="wish-list">
              <!-- 待审批 -->
              <template v-if="pendingReviewWishes.length > 0">
                <h4 class="wish-group-title">{{ t('baby.wishGroupPending') }}</h4>
                <div
                  v-for="wish in pendingReviewWishes"
                  :key="wish.id"
                  class="wish-card"
                  role="button"
                  tabindex="0"
                  @click="openWishDetail(wish)"
                  @keydown.enter="openWishDetail(wish)"
                  @keydown.space.prevent="openWishDetail(wish)"
                >
                  <div class="wish-card-top">
                    <span class="wish-emoji-icon">{{ wish.emoji || '🌟' }}</span>
                    <div class="wish-card-info">
                      <span class="wish-name">{{ wish.name }}</span>
                    </div>
                    <van-tag :type="getWishStatusType(wish.status)">{{ getWishStatusLabel(wish.status) }}</van-tag>
                  </div>
                  <div class="wish-meta-row">
                    <span v-if="wish.star_coin_cost" class="wish-cost">{{ wish.star_coin_cost }} ⭐</span>
                    <span v-else class="wish-cost wish-cost--unset">— ⭐</span>
                    <span class="wish-owner">{{ wish.child_display_name }}</span>
                    <span class="priority-icon" :class="wish.priority">{{ priorityShortLabel(wish.priority) }}</span>
                  </div>
                  <p v-if="wish.description" class="wish-desc-text">{{ truncateDesc(wish.description) }}</p>
                  <div v-if="wish.status === 'pending_review'" class="card-actions">
                    <button class="action-btn action-btn--success" :disabled="actioningId === wish.id" @click.stop="openApprove(wish)">
                      <IIcon icon="mdi:check-circle" size="16" />
                      <span>{{ t('baby.wishApprove') }}</span>
                    </button>
                    <button class="action-btn action-btn--danger" :disabled="actioningId === wish.id" @click.stop="openReject(wish)">
                      <IIcon icon="mdi:close-circle" size="16" />
                      <span>{{ t('baby.wishReject') }}</span>
                    </button>
                  </div>
                  <div v-else-if="wish.status === 'redemption_requested'" class="card-actions">
                    <button class="action-btn action-btn--success" :disabled="actioningId === wish.id" @click.stop="openRealize(wish)">
                      <IIcon icon="mdi:gift" size="16" />
                      <span>{{ t('baby.wishRealize') }}</span>
                    </button>
                    <button class="action-btn action-btn--muted" :disabled="actioningId === wish.id" @click.stop="doDefer(wish.id)">
                      <IIcon icon="mdi:clock-outline" size="16" />
                      <span>{{ t('baby.wishDefer') }}</span>
                    </button>
                  </div>
                </div>
              </template>

              <!-- 待实现 -->
              <template v-if="activeWishes.length > 0">
                <h4 class="wish-group-title">{{ t('baby.wishGroupActive') }}</h4>
                <div
                  v-for="wish in activeWishes"
                  :key="wish.id"
                  class="wish-card"
                  role="button"
                  tabindex="0"
                  @click="openWishDetail(wish)"
                  @keydown.enter="openWishDetail(wish)"
                  @keydown.space.prevent="openWishDetail(wish)"
                >
                  <div class="wish-card-top">
                    <span class="wish-emoji-icon">{{ wish.emoji || '🌟' }}</span>
                    <div class="wish-card-info">
                      <span class="wish-name">{{ wish.name }}</span>
                    </div>
                    <van-tag :type="getWishStatusType(wish.status)">{{ getWishStatusLabel(wish.status) }}</van-tag>
                  </div>
                  <div class="wish-meta-row">
                    <span v-if="wish.star_coin_cost" class="wish-cost">{{ wish.star_coin_cost }} ⭐</span>
                    <span v-else class="wish-cost wish-cost--unset">— ⭐</span>
                    <span class="wish-owner">{{ wish.child_display_name }}</span>
                    <span class="priority-icon" :class="wish.priority">{{ priorityShortLabel(wish.priority) }}</span>
                  </div>
                  <p v-if="wish.description" class="wish-desc-text">{{ truncateDesc(wish.description) }}</p>
                  <van-progress
                    v-if="wish.star_coin_cost"
                    :percentage="Math.min(Math.round(((childBalances[wish.child_user_id] ?? 0) / wish.star_coin_cost) * 100), 100)"
                    stroke-width="6"
                    color="#f5a623"
                  />
                  <div v-if="(wish.star_coin_cost ?? 0) > 0" class="card-actions">
                    <button class="action-btn action-btn--primary" @click.stop="openEditCost(wish)">
                      <IIcon icon="mdi:pencil" size="16" />
                      <span>{{ t('baby.wishEditCost') }}</span>
                    </button>
                  </div>
                </div>
              </template>

              <!-- 已实现 -->
              <template v-if="fulfilledWishes.length > 0">
                <h4 class="wish-group-title">{{ t('baby.wishGroupFulfilled') }}</h4>
                <div
                  v-for="wish in fulfilledWishes"
                  :key="wish.id"
                  class="wish-card wish-card--fulfilled"
                  role="button"
                  tabindex="0"
                  @click="openWishDetail(wish)"
                  @keydown.enter="openWishDetail(wish)"
                  @keydown.space.prevent="openWishDetail(wish)"
                >
                  <div class="wish-card-top">
                    <span class="wish-emoji-icon">{{ wish.emoji || '🌟' }}</span>
                    <div class="wish-card-info">
                      <span class="wish-name">{{ wish.name }}</span>
                    </div>
                    <van-tag :type="getWishStatusType(wish.status)">{{ getWishStatusLabel(wish.status) }}</van-tag>
                  </div>
                  <div class="wish-meta-row">
                    <span v-if="wish.star_coin_cost" class="wish-cost">{{ wish.star_coin_cost }} ⭐</span>
                    <span v-else class="wish-cost wish-cost--unset">— ⭐</span>
                    <span class="wish-owner">{{ wish.child_display_name }}</span>
                    <span class="priority-icon" :class="wish.priority">{{ priorityShortLabel(wish.priority) }}</span>
                  </div>
                  <p v-if="wish.description" class="wish-desc-text">{{ truncateDesc(wish.description) }}</p>
                  <p v-if="wish.rejection_reason" class="wish-rejection">{{ t('baby.wishRejectionReasonLabel') }}：{{ wish.rejection_reason }}</p>
                </div>
              </template>

              <EmptyState v-if="filteredWishes.length === 0" :description="t('baby.noWishes')" image-size="60" />
            </div>
          </van-tab>

          <van-tab :title="t('baby.tabChores')">
            <div class="chore-list">
              <!-- 待审批 -->
              <template v-if="pendingApprovalChores.length > 0">
                <h4 class="wish-group-title">{{ t('baby.choreGroupPendingApproval') }}</h4>
                <div
                  v-for="chore in pendingApprovalChores"
                  :key="chore.id"
                  class="chore-card"
                >
                  <div class="chore-card-top">
                    <span class="chore-emoji-icon">{{ chore.chore_emoji || '📋' }}</span>
                    <div class="chore-card-info">
                      <span class="chore-name">{{ chore.chore_name }}</span>
                    </div>
                    <van-tag :type="getChoreStatusType(chore.status)">{{ getChoreStatusLabel(chore.status) }}</van-tag>
                  </div>
                  <div class="chore-meta-row">
                    <span class="chore-assignee">{{ getChoreAssignee(chore) }}</span>
                    <span class="chore-reward-inline">+{{ chore.coin_reward }}⭐</span>
                    <template v-if="chore.streak_count > 0">
                      <span class="chore-streak-icon">🔥{{ chore.streak_count }}</span>
                    </template>
                  </div>
                  <div class="card-actions">
                    <button
                      class="action-btn action-btn--success"
                      :disabled="actioningId === chore.id"
                      @click.stop="doApproveChore(chore)"
                    >
                      <IIcon icon="mdi:check-circle" size="16" />
                      <span>{{ t('baby.choreApprove') }}</span>
                    </button>
                    <button
                      class="action-btn action-btn--danger"
                      :disabled="actioningId === chore.id"
                      @click.stop="doRejectChore(chore)"
                    >
                      <IIcon icon="mdi:close-circle" size="16" />
                      <span>{{ t('baby.choreRedo') }}</span>
                    </button>
                  </div>
                </div>
              </template>

              <!-- 待完成 -->
              <template v-if="availableChores.length > 0">
                <h4 class="wish-group-title">{{ t('baby.choreGroupAvailable') }}</h4>
                <div
                  v-for="chore in availableChores"
                  :key="chore.id"
                  class="chore-card"
                >
                  <div class="chore-card-top">
                    <span class="chore-emoji-icon">{{ chore.chore_emoji || '📋' }}</span>
                    <div class="chore-card-info">
                      <span class="chore-name">{{ chore.chore_name }}</span>
                    </div>
                    <van-tag :type="getChoreStatusType(chore.status)">{{ getChoreStatusLabel(chore.status) }}</van-tag>
                  </div>
                  <div class="chore-meta-row">
                    <span class="chore-assignee">{{ getChoreAssignee(chore) }}</span>
                    <span class="chore-reward-inline">+{{ chore.coin_reward }}⭐</span>
                    <template v-if="chore.streak_count > 0">
                      <span class="chore-streak-icon">🔥{{ chore.streak_count }}</span>
                    </template>
                  </div>
                  <div class="card-actions">
                    <template v-if="chore.is_pool_unclaimed">
                      <button
                        class="action-btn action-btn--primary"
                        :disabled="assigningId === chore.id"
                        @click.stop="openAssignPicker(chore)"
                      >
                        <IIcon icon="mdi:account-group" size="16" />
                        <span v-if="assigningId === chore.id">{{ t('baby.choreAssigning') }}</span>
                        <span v-else>{{ t('baby.choreAssign') }}</span>
                      </button>
                    </template>
                    <template v-else>
                      <button
                        class="action-btn action-btn--primary"
                        :disabled="assigningId === chore.id || voidingId === chore.id"
                        @click.stop="openAssignPicker(chore)"
                      >
                        <IIcon icon="mdi:swap-horizontal" size="16" />
                        <span v-if="assigningId === chore.id">{{ t('baby.choreAssigning') }}</span>
                        <span v-else>{{ t('baby.choreReassign') }}</span>
                      </button>
                      <button
                        class="action-btn action-btn--danger"
                        :disabled="assigningId === chore.id || voidingId === chore.id"
                        @click.stop="doVoidChore(chore)"
                      >
                        <IIcon icon="mdi:delete-circle" size="16" />
                        <span v-if="voidingId === chore.id">{{ t('baby.choreVoiding') }}</span>
                        <span v-else>{{ t('baby.choreVoid') }}</span>
                      </button>
                    </template>
                  </div>
                </div>
              </template>

              <!-- 已完成 -->
              <template v-if="completedChores.length > 0">
                <h4 class="wish-group-title">{{ t('baby.choreGroupCompleted') }}</h4>
                <div
                  v-for="chore in completedChores"
                  :key="chore.id"
                  class="chore-card chore-card--completed"
                >
                  <div class="chore-card-top">
                    <span class="chore-emoji-icon">{{ chore.chore_emoji || '📋' }}</span>
                    <div class="chore-card-info">
                      <span class="chore-name">{{ chore.chore_name }}</span>
                    </div>
                    <van-tag :type="getChoreStatusType(chore.status)">{{ getChoreStatusLabel(chore.status) }}</van-tag>
                  </div>
                  <div class="chore-meta-row">
                    <span class="chore-assignee">{{ getChoreAssignee(chore) }}</span>
                    <span class="chore-reward-inline">+{{ chore.coin_reward }}⭐</span>
                    <template v-if="chore.streak_count > 0">
                      <span class="chore-streak-icon">🔥{{ chore.streak_count }}</span>
                    </template>
                  </div>
                </div>
              </template>

              <!-- 已拒绝 -->
              <template v-if="rejectedChores.length > 0">
                <h4 class="wish-group-title">{{ t('baby.choreGroupRejected') }}</h4>
                <div
                  v-for="chore in rejectedChores"
                  :key="chore.id"
                  class="chore-card chore-card--completed"
                >
                  <div class="chore-card-top">
                    <span class="chore-emoji-icon">{{ chore.chore_emoji || '📋' }}</span>
                    <div class="chore-card-info">
                      <span class="chore-name">{{ chore.chore_name }}</span>
                    </div>
                    <van-tag :type="getChoreStatusType(chore.status)">{{ getChoreStatusLabel(chore.status) }}</van-tag>
                  </div>
                  <div class="chore-meta-row">
                    <span class="choreAssignee">{{ getChoreAssignee(chore) }}</span>
                    <span class="chore-reward-inline">+{{ chore.coin_reward }}⭐</span>
                  </div>
                </div>
              </template>

              <EmptyState v-if="filteredChores.length === 0" :description="t('baby.noChores')" image-size="60" />
            </div>

            <!-- FAB: create new chore -->
            <div class="fab" :aria-label="t('baby.addChore')" role="button" tabindex="0" @click="$router.push('/baby/chores/new')" @keydown.enter="$router.push('/baby/chores/new')" @keydown.space.prevent="$router.push('/baby/chores/new')">
              <IIcon icon="mdi:plus" size="22" />
            </div>
          </van-tab>
        </van-tabs>

        <!-- Child picker popup (shown when on 全部 tab) -->
        <van-popup v-model:show="showChildPicker" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ t('baby.grantSelectChild') }}</p>
          <van-cell
            v-for="child in childMembers"
            :key="child.id"
            :title="child.display_name"
            is-link
            @click="selectChildAndGrant(child)"
          >
            <template #icon>
              <div class="child-tab-avatar" :style="{ background: child.avatar_color || '#FF6B6B', marginRight: '8px' }">
                {{ (child.display_name ?? '?').charAt(0) }}
              </div>
            </template>
          </van-cell>
        </van-popup>

        <!-- Grant stars bottom sheet -->
        <van-popup v-model:show="showGrantSheet" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ t('baby.grantSheetTitle', { name: grantTargetChild?.display_name }) }}</p>
          <van-field
            v-model="grantAmountStr"
            type="digit"
            :label="t('baby.grantAmountLabel')"
            :placeholder="t('baby.grantAmountPlaceholder')"
            class="grant-field"
          />
          <van-field
            v-model="grantReason"
            :label="t('baby.grantReasonLabel')"
            :placeholder="t('baby.grantReasonPlaceholder')"
            class="grant-field"
          />
          <van-button
            block
            type="primary"
            :disabled="!grantAmountStr || parseInt(grantAmountStr, 10) <= 0"
            :loading="grantingCoins"
            class="grant-confirm-btn"
            @click="doGrant"
          >{{ t('baby.grantConfirm') }}</van-button>
        </van-popup>

        <!-- Assign chore picker popup -->
        <van-popup v-model:show="showAssignPicker" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ assigningChore?.is_pool_unclaimed ? t('baby.assignPickerTitle') : t('baby.reassignPickerTitle') }}</p>
          <van-cell
            v-for="child in childMembers.filter(c => c.is_active)"
            :key="child.id"
            :title="child.display_name"
            is-link
            @click="selectChildForAssign(child)"
          >
            <template #icon>
              <div class="child-tab-avatar" :style="{ background: child.avatar_color || '#FF6B6B', marginRight: '8px' }">
                {{ (child.display_name ?? '?').charAt(0) }}
              </div>
            </template>
          </van-cell>
        </van-popup>

        <!-- Wish detail bottom sheet -->
        <van-popup v-model:show="showWishDetail" position="bottom" round style="padding: 24px 16px 40px">
          <template v-if="detailWish">
            <h3 class="sheet-title">{{ detailWish.emoji || '🌟' }} {{ detailWish.name }}</h3>
            <div class="detail-row">
              <span class="detail-label">{{ t('baby.wishDetailOwner') }}</span>
              <span class="detail-value">{{ detailWish.child_display_name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">{{ t('baby.wishDetailStatus') }}</span>
              <van-tag :type="getWishStatusType(detailWish.status)">{{ getWishStatusLabel(detailWish.status) }}</van-tag>
            </div>
            <div class="detail-row">
              <span class="detail-label">{{ t('baby.wishDetailPriority') }}</span>
              <span class="priority-icon" :class="detailWish.priority">{{ priorityFullLabel(detailWish.priority) }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">{{ t('baby.wishDetailCost') }}</span>
              <span class="detail-value">{{ detailWish.star_coin_cost != null ? `${detailWish.star_coin_cost} ⭐` : '— ⭐' }}</span>
            </div>
            <div v-if="detailWish.description" class="detail-desc">
              <span class="detail-label">{{ t('baby.wishDetailDesc') }}</span>
              <p class="detail-desc-text">{{ detailWish.description }}</p>
            </div>
            <p v-if="detailWish.rejection_reason" class="wish-rejection">{{ t('baby.wishRejectionReasonLabel') }}：{{ detailWish.rejection_reason }}</p>
            <div class="detail-actions">
              <template v-if="detailWish.status === 'pending_review'">
                <button class="btn-cancel" @click="showWishDetail = false">{{ t('baby.wishCancel') }}</button>
                <button class="btn-reject-confirm" :disabled="actioning" @click="openReject(detailWish)">{{ t('baby.wishReject') }}</button>
                <button class="btn-submit" :disabled="actioning" @click="openApprove(detailWish)">{{ t('baby.wishApprove') }}</button>
              </template>
              <template v-else-if="detailWish.status === 'redemption_requested'">
                <button class="btn-cancel" @click="showWishDetail = false">{{ t('baby.wishCancel') }}</button>
                <button class="btn-reject-confirm" :disabled="actioning" @click="openReject(detailWish)">{{ t('baby.wishReject') }}</button>
                <button class="btn-realize-confirm" :disabled="actioning" @click="openRealize(detailWish)">{{ t('baby.wishRealize') }}</button>
              </template>
              <template v-else>
                <button class="btn-cancel" style="flex:1" @click="showWishDetail = false">{{ t('baby.wishCancel') }}</button>
              </template>
            </div>
          </template>
        </van-popup>

        <!-- Approve dialog -->
        <van-popup v-model:show="showApproveDialog" position="bottom" round style="padding: 24px 16px 40px">
          <template v-if="approveTarget">
            <h3 class="sheet-title"><IIcon icon="mdi:check-circle" size="20" color="var(--color-success)" /> {{ t('baby.wishApproveTitle') }}</h3>
            <p class="dialog-desc">{{ t('baby.wishApproveDesc', { name: approveTarget.name }) }}</p>
            <div class="cost-field">
              <span class="cost-label">{{ t('baby.wishCostLabel') }}</span>
              <van-field
                v-model="approveCostInput"
                type="number"
                input-align="right"
                :placeholder="t('baby.wishCostPlaceholder')"
                class="cost-input-field"
              />
            </div>
            <StarCoinSuggestion
              :child-id="approveTarget.child_user_id"
              @select="approveCostInput = String($event)"
            />
            <div v-if="wishDialogError" class="error-msg">{{ wishDialogError }}</div>
            <div class="detail-actions">
              <button class="btn-cancel" @click="showApproveDialog = false">{{ t('baby.wishCancel') }}</button>
              <button class="btn-submit" :disabled="actioning || !isApproveCostValid" @click="doApprove">{{ t('baby.wishConfirmApprove') }}</button>
            </div>
          </template>
        </van-popup>

        <!-- Reject dialog -->
        <van-popup v-model:show="showRejectDialog" position="bottom" round style="padding: 24px 16px 40px">
          <template v-if="rejectTarget">
            <h3 class="sheet-title"><IIcon icon="mdi:close-circle" size="20" color="#dc3545" /> {{ t('baby.wishRejectTitle') }}</h3>
            <p class="dialog-desc">{{ t('baby.wishRejectDesc', { name: rejectTarget.name }) }}</p>
            <input v-model="rejectReason" class="input" :placeholder="t('baby.wishRejectReasonPlaceholder')" maxlength="200" />
            <div v-if="wishDialogError" class="error-msg">{{ wishDialogError }}</div>
            <div class="detail-actions">
              <button class="btn-cancel" @click="showRejectDialog = false">{{ t('baby.wishCancel') }}</button>
              <button class="btn-reject-confirm" :disabled="actioning" @click="doReject">{{ t('baby.wishConfirmReject') }}</button>
            </div>
          </template>
        </van-popup>

        <!-- Realize dialog -->
        <van-popup v-model:show="showRealizeDialog" position="bottom" round style="padding: 24px 16px 40px">
          <template v-if="realizeTarget">
            <h3 class="sheet-title">{{ t('baby.wishRealizeTitle') }}</h3>
            <p class="dialog-desc">{{ t('baby.wishRealizeDesc', { name: realizeTarget.name, cost: realizeTarget.star_coin_cost }) }}</p>
            <div v-if="wishDialogError" class="error-msg">{{ wishDialogError }}</div>
            <div class="detail-actions">
              <button class="btn-cancel" @click="showRealizeDialog = false">{{ t('baby.wishCancel') }}</button>
              <button class="btn-realize-confirm" :disabled="actioning" @click="doRealize">{{ t('baby.wishConfirmRealize') }}</button>
            </div>
          </template>
        </van-popup>

        <!-- Cost-edit dialog -->
        <WishCostEditDialog
          v-if="editCostTarget"
          :visible="editCostVisible"
          :wish="editCostTarget"
          @update:visible="editCostVisible = $event"
          @saved="onCostEditSaved"
        />
      </template>
    </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Baby' })
import { ref, computed, onMounted } from 'vue'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { useChoreStore } from '@/stores/chore'
import { useBlindBoxStore } from '@/stores/blindBox'
import PageHeader from '@/components/common/PageHeader.vue'
import PendingApprovalsSection from '@/components/dashboard/PendingApprovalsSection.vue'
import ChildCalendar from '@/components/calendar/ChildCalendar.vue'
import { getAllChildBalances, getChildrenChoreStats, type ChoreStats } from '@/api/family'
import { listParentChildWishes, approveChildWish, rejectChildWish, realizeChildWish, deferChildWish, type ParentWish } from '@/api/childWishes'
import { getFamilyChildCalendar } from '@/api/calendar'
import { grantCoins } from '@/api/coins'
import { getChildrenChores, assignChoreInstance, voidChoreInstance, approveChore, rejectChore, type ChoreInstance } from '@/api/chores'
import WishCostEditDialog from '@/components/wishes/WishCostEditDialog.vue'
import StarCoinSuggestion from '@/components/wishes/StarCoinSuggestion.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import BabyPageSkeleton from '@/components/baby/BabyPageSkeleton.vue'
import IIcon from '@/components/IIcon.vue'

const { t } = useI18n()
const authStore = useAuthStore()
const familyStore = useFamilyStore()
const choreStore = useChoreStore()
const blindBoxStore = useBlindBoxStore()

const pendingDrawCount = computed(
  () => blindBoxStore.draws.filter((d) => d.status === 'pending_fulfillment').length,
)

const refreshing = ref(false)
const loading = ref(true)
const activeChildIndex = ref(0)
const activeContentTab = ref(0)

// Grant stars state
const showChildPicker = ref(false)
const showGrantSheet = ref(false)
const grantTargetChild = ref<{ id: string; display_name: string } | null>(null)
const grantAmountStr = ref('')
const grantReason = ref('')
const grantingCoins = ref(false)

// Assign/void chore state
const showAssignPicker = ref(false)
const assigningChore = ref<ChoreInstance | null>(null)
const assigningId = ref<string | null>(null)
const voidingId = ref<string | null>(null)

const childBalances = ref<Record<string, number>>({})
const childChoreStats = ref<Record<string, ChoreStats>>({})
const allWishes = ref<ParentWish[]>([])

const allChores = ref<ChoreInstance[]>([])

const childMembers = computed(() => familyStore.members.filter(m => m.role === 'child'))

const selectedChildId = computed(() => {
  if (activeChildIndex.value === 0) return null // "全部"
  const child = childMembers.value[activeChildIndex.value - 1]
  return child?.id ?? null
})

const currentBalance = computed(() => {
  if (!selectedChildId.value) {
    return Object.values(childBalances.value).reduce((sum, val) => sum + val, 0)
  }
  return childBalances.value[selectedChildId.value] ?? 0
})

const currentChoreStats = computed(() => {
  if (!selectedChildId.value) {
    const all = Object.values(childChoreStats.value)
    return {
      completed_this_week: all.reduce((sum, s) => sum + (s.completed_this_week ?? 0), 0),
      total_this_week: all.reduce((sum, s) => sum + (s.total_this_week ?? 0), 0),
    }
  }
  return childChoreStats.value[selectedChildId.value] ?? { completed_this_week: 0, total_this_week: 0 }
})

const currentWishCount = computed(() => {
  const wishes = selectedChildId.value
    ? allWishes.value.filter(w => w.child_user_id === selectedChildId.value)
    : allWishes.value
  return wishes.filter(w => ['pending_review', 'active', 'redemption_requested'].includes(w.status)).length
})

const filteredWishes = computed(() => {
  const base = selectedChildId.value
    ? allWishes.value.filter(w => w.child_user_id === selectedChildId.value)
    : allWishes.value
  return base
})

const priorityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 }

function sortWishes(wishes: ParentWish[]): ParentWish[] {
  return [...wishes].sort((a, b) => {
    const pDiff = (priorityOrder[a.priority] ?? 9) - (priorityOrder[b.priority] ?? 9)
    if (pDiff !== 0) return pDiff
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  })
}

const pendingReviewWishes = computed(() =>
  sortWishes(filteredWishes.value.filter(w => ['pending_review', 'redemption_requested'].includes(w.status))),
)

const activeWishes = computed(() =>
  sortWishes(filteredWishes.value.filter(w => w.status === 'active')),
)

const fulfilledWishes = computed(() =>
  sortWishes(filteredWishes.value.filter(w => ['fulfilled', 'realized'].includes(w.status))),
)

// Wish review state
const actioningId = ref<string | null>(null)
const actioning = ref(false)
const wishDialogError = ref('')
const showWishDetail = ref(false)
const detailWish = ref<ParentWish | null>(null)
const showApproveDialog = ref(false)
const approveTarget = ref<ParentWish | null>(null)
const approveCostInput = ref('')
const isApproveCostValid = computed(() => {
  const n = Number(approveCostInput.value)
  return Number.isFinite(n) && n >= 1 && Math.floor(n) === n
})
const showRejectDialog = ref(false)
const rejectTarget = ref<ParentWish | null>(null)
const rejectReason = ref('')
const showRealizeDialog = ref(false)
const realizeTarget = ref<ParentWish | null>(null)
const editCostTarget = ref<ParentWish | null>(null)
const editCostVisible = ref(false)

function truncateDesc(desc: string, max = 50): string {
  return desc.length > max ? desc.slice(0, max) + '...' : desc
}

function priorityShortLabel(p: string): string {
  const map: Record<string, string> = { high: t('baby.wishPriorityHighShort'), medium: t('baby.wishPriorityMediumShort'), low: t('baby.wishPriorityLowShort') }
  return map[p] ?? p
}

function priorityFullLabel(p: string): string {
  const map: Record<string, string> = { high: t('baby.wishPriorityHigh'), medium: t('baby.wishPriorityMedium'), low: t('baby.wishPriorityLow') }
  return map[p] ?? p
}

function openWishDetail(wish: ParentWish) {
  detailWish.value = wish
  showWishDetail.value = true
}

function openApprove(wish: ParentWish) {
  approveTarget.value = wish
  approveCostInput.value = wish.star_coin_cost != null ? String(wish.star_coin_cost) : ''
  wishDialogError.value = ''
  showWishDetail.value = false
  showApproveDialog.value = true
}

function openReject(wish: ParentWish) {
  rejectTarget.value = wish
  rejectReason.value = ''
  wishDialogError.value = ''
  showWishDetail.value = false
  showRejectDialog.value = true
}

function openRealize(wish: ParentWish) {
  realizeTarget.value = wish
  wishDialogError.value = ''
  showWishDetail.value = false
  showRealizeDialog.value = true
}

async function doApprove() {
  if (!approveTarget.value) return
  const cost = Math.round(Number(approveCostInput.value))
  if (!Number.isFinite(cost) || cost < 1) return
  actioning.value = true
  wishDialogError.value = ''
  try {
    await approveChildWish(approveTarget.value.id, cost)
    showApproveDialog.value = false
    showSuccessToast(t('toast.wishApproved'))
    await loadData()
  } catch {
    wishDialogError.value = t('baby.wishOperationFailed')
  } finally {
    actioning.value = false
  }
}

async function doReject() {
  if (!rejectTarget.value) return
  actioning.value = true
  wishDialogError.value = ''
  try {
    await showConfirmDialog({
      title: t('baby.wishRejectTitle'),
      message: t('baby.wishRejectConfirmMsg', { name: rejectTarget.value.name }),
    })
  } catch {
    actioning.value = false
    return
  }
  try {
    await rejectChildWish(rejectTarget.value.id, rejectReason.value || undefined)
    showRejectDialog.value = false
    showSuccessToast(t('toast.wishRejected'))
    await loadData()
  } catch {
    wishDialogError.value = t('baby.wishOperationFailed')
  } finally {
    actioning.value = false
  }
}

async function doRealize() {
  if (!realizeTarget.value) return
  actioning.value = true
  wishDialogError.value = ''
  try {
    await realizeChildWish(realizeTarget.value.id)
    showRealizeDialog.value = false
    showSuccessToast(t('toast.wishRealized'))
    await loadData()
  } catch {
    wishDialogError.value = t('baby.wishOperationFailed')
  } finally {
    actioning.value = false
  }
}

async function doDefer(wishId: string) {
  actioningId.value = wishId
  try {
    await deferChildWish(wishId)
    showSuccessToast(t('toast.wishDeferred'))
    await loadData()
  } catch {
    showFailToast(t('baby.wishOperationFailed'))
  } finally {
    actioningId.value = null
  }
}

function openEditCost(wish: ParentWish) {
  editCostTarget.value = wish
  editCostVisible.value = true
}

function onCostEditSaved() {
  editCostTarget.value = null
  loadData()
}

const filteredChores = computed(() => {
  const base = selectedChildId.value
    ? allChores.value.filter(c => c.child_user_id === String(selectedChildId.value))
    : allChores.value
  return base
})

const pendingApprovalChores = computed(() =>
  [...filteredChores.value.filter(c => c.status === 'pending_approval')].sort((a, b) => {
    const ta = a.submitted_at ? new Date(a.submitted_at).getTime() : 0
    const tb = b.submitted_at ? new Date(b.submitted_at).getTime() : 0
    return tb - ta
  }),
)

const availableChores = computed(() =>
  [...filteredChores.value.filter(c => c.status === 'available')].sort((a, b) => {
    const ta = a.claimed_at ? new Date(a.claimed_at).getTime() : 0
    const tb = b.claimed_at ? new Date(b.claimed_at).getTime() : 0
    return ta - tb
  }),
)

const completedChores = computed(() =>
  [...filteredChores.value.filter(c => c.status === 'approved')].sort((a, b) => {
    const ta = a.approved_at ? new Date(a.approved_at).getTime() : 0
    const tb = b.approved_at ? new Date(b.approved_at).getTime() : 0
    return tb - ta
  }),
)

const rejectedChores = computed(() =>
  [...filteredChores.value.filter(c => c.status === 'rejected')],
)

function getChoreAssignee(chore: ChoreInstance): string {
  if (chore.is_pool_unclaimed) return t('baby.choreUnclaimed')
  const child = getChildForChore(chore)
  return child?.display_name ?? '?'
}

const weeklyCompletionRate = computed(() => {
  const stats = currentChoreStats.value
  if (!stats.total_this_week) return 0
  return Math.round((stats.completed_this_week / stats.total_this_week) * 100)
})

const calendarChildId = computed<string | null>(() => {
  if (selectedChildId.value) return String(selectedChildId.value)
  // 全部视图时取第一个孩子
  const first = childMembers.value[0]
  return first ? String(first.id) : null
})

// B4: in 全部 mode the calendar silently shows the first child; surface
// that via a hint. null in per-child mode (no hint needed).
const calendarDisplayHint = computed<string | null>(() => {
  if (selectedChildId.value) return null
  const first = childMembers.value[0]
  return first?.display_name ?? null
})

function fetchCalendarMonth(year: number, month: number) {
  if (!calendarChildId.value) return Promise.reject(new Error('no child'))
  return getFamilyChildCalendar(calendarChildId.value, year, month)
}

function getWishStatusType(status: string): 'primary' | 'success' | 'warning' | 'danger' | 'default' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'default'> = {
    pending_review: 'warning',
    active: 'primary',
    redemption_requested: 'warning',
    fulfilled: 'success',
    realized: 'success',
    rejected: 'danger',
  }
  return map[status] ?? 'default'
}

function getWishStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending_review: t('baby.wishStatusPendingReview'),
    active: t('baby.wishStatusActive'),
    redemption_requested: t('baby.wishStatusRedemptionRequested'),
    fulfilled: t('baby.wishStatusFulfilled'),
    realized: t('baby.wishStatusFulfilled'),
    rejected: t('baby.wishStatusRejected'),
  }
  return map[status] ?? status
}

function getChoreStatusType(status: string): 'primary' | 'success' | 'warning' | 'danger' | 'default' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'default'> = {
    available: 'default',
    pending_approval: 'warning',
    approved: 'success',
    rejected: 'danger',
  }
  return map[status] ?? 'default'
}

function getChoreStatusLabel(status: string): string {
  const map: Record<string, string> = {
    available: t('baby.chorePending'),
    pending_approval: t('baby.wishStatusPendingReview'),
    approved: t('baby.choreCompleted'),
    rejected: t('baby.wishStatusRejected'),
  }
  return map[status] ?? status
}

function getChildForChore(chore: ChoreInstance) {
  if (!chore.child_user_id || chore.is_pool_unclaimed) return null
  return childMembers.value.find(m => String(m.id) === chore.child_user_id) ?? null
}

function openGrantSheet() {
  if (!selectedChildId.value) {
    // 全部视图：先选孩子
    showChildPicker.value = true
  } else {
    const child = childMembers.value.find(c => c.id === selectedChildId.value)
    if (!child) return
    grantTargetChild.value = { id: String(child.id), display_name: child.display_name ?? '' }
    grantAmountStr.value = ''
    grantReason.value = ''
    showGrantSheet.value = true
  }
}

function selectChildAndGrant(child: { id: string | number; display_name?: string | null }) {
  showChildPicker.value = false
  grantTargetChild.value = { id: String(child.id), display_name: child.display_name ?? '' }
  grantAmountStr.value = ''
  grantReason.value = ''
  showGrantSheet.value = true
}

async function doGrant() {
  const amount = parseInt(grantAmountStr.value, 10)
  if (!grantTargetChild.value || !amount || amount <= 0) return
  grantingCoins.value = true
  try {
    await grantCoins(grantTargetChild.value.id, amount, grantReason.value || t('baby.grantDefaultReason'))
    showSuccessToast(t('toast.childGrantedStars', { amount, name: grantTargetChild.value.display_name }))
    showGrantSheet.value = false
  } catch {
    showFailToast(t('toast.grantFailed'))
    return
  } finally {
    grantingCoins.value = false
  }
  try {
    const res = await getAllChildBalances()
    childBalances.value = res.data
  } catch { showFailToast(t('toast.operationFailed')) }
}

function openAssignPicker(chore: ChoreInstance) {
  assigningChore.value = chore
  showAssignPicker.value = true
}

async function selectChildForAssign(child: { id: string | number; display_name?: string | null }) {
  if (!assigningChore.value) return
  const isReassign = !assigningChore.value.is_pool_unclaimed
  showAssignPicker.value = false
  assigningId.value = assigningChore.value.id
  try {
    const updated = await assignChoreInstance(assigningChore.value.id, String(child.id))
    // Update the chore in allChores
    const idx = allChores.value.findIndex(c => c.id === updated.id)
    if (idx >= 0) {
      allChores.value[idx] = updated
    }
    showSuccessToast(isReassign ? t('baby.choreReassignSuccess') : t('baby.choreAssignSuccess'))
  } catch {
    showFailToast(isReassign ? t('baby.choreReassignFailed') : t('baby.choreAssignFailed'))
  } finally {
    assigningId.value = null
    assigningChore.value = null
  }
}

async function doApproveChore(chore: ChoreInstance) {
  try {
    await showConfirmDialog({
      title: t('baby.choreApprove'),
      message: t('baby.choreApproveConfirm', { name: chore.chore_name }),
    })
  } catch {
    return
  }
  actioningId.value = chore.id
  try {
    await approveChore(chore.id)
    showSuccessToast(t('baby.choreApproveSuccess'))
    await loadData()
  } catch (err) {
    // Idempotent: if the chore was already approved (e.g. approved from the
    // header section while the task tab still shows it as actionable), treat
    // as success — show a friendly toast and refresh instead of an error.
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 422 || status === 409) {
      await loadData()
      const fresh = allChores.value.find(c => c.id === chore.id)
      if (fresh?.status === 'approved') {
        showSuccessToast(t('baby.choreAlreadyApproved'))
        return
      }
    }
    showFailToast(t('baby.choreApproveFailed'))
  } finally {
    actioningId.value = null
  }
}

async function doRejectChore(chore: ChoreInstance) {
  try {
    await showConfirmDialog({
      title: t('baby.choreRedo'),
      message: t('baby.choreRedoConfirm', { name: chore.chore_name }),
    })
  } catch {
    return
  }
  actioningId.value = chore.id
  try {
    await rejectChore(chore.id, true)
    showSuccessToast(t('baby.choreRedoSuccess'))
    await loadData()
  } catch {
    showFailToast(t('baby.choreRedoFailed'))
  } finally {
    actioningId.value = null
  }
}

async function doVoidChore(chore: ChoreInstance) {
  try {
    await showConfirmDialog({
      title: t('baby.voidChoreTitle'),
      message: t('baby.voidChoreMessage', { name: chore.chore_name }),
    })
  } catch {
    // User cancelled
    return
  }
  voidingId.value = chore.id
  // Optimistic removal
  const idx = allChores.value.findIndex(c => c.id === chore.id)
  const backup = allChores.value[idx]
  if (idx >= 0) {
    allChores.value.splice(idx, 1)
  }
  try {
    await voidChoreInstance(chore.id)
    showSuccessToast(t('baby.choreVoidSuccess'))
  } catch {
    // Re-add on error
    if (idx >= 0 && backup) {
      allChores.value.splice(idx, 0, backup)
    }
    showFailToast(t('baby.choreVoidFailed'))
  } finally {
    voidingId.value = null
  }
}

async function loadData() {
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  try {
    const [balances, stats, wishes, chores] = await Promise.all([
      getAllChildBalances(),
      getChildrenChoreStats(),
      listParentChildWishes(),
      getChildrenChores(today),
    ])
    childBalances.value = balances.data
    childChoreStats.value = stats.data
    allWishes.value = wishes
    allChores.value = chores
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

async function onRefresh() {
  const tasks = [
    familyStore.fetchFamily(),
    loadData(),
  ]
  if (authStore.user?.role === 'owner') {
    tasks.push(choreStore.fetchPendingApprovals())
  }
  await Promise.all(tasks)
  refreshing.value = false
}

onMounted(async () => {
  loading.value = true
  await familyStore.fetchFamily()
  if (authStore.user?.role === 'owner') {
    await choreStore.fetchPendingApprovals()
  }
  await loadData()
  await blindBoxStore.fetchDraws()
  loading.value = false
})
</script>

<style scoped>
.baby-page {
  min-height: 100vh;
  padding-bottom: 20px;
}

/* Child tab custom title */
.child-tab-title {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 5px;
  padding: 2px 2px;
}

.child-tab-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.child-tab-name {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60px;
}

/* Fix tab text visibility in dark mode */
.child-tabs :deep(.van-tab) {
  color: var(--van-gray-6, #969799);
}

.child-tabs :deep(.van-tab--active) {
  color: var(--van-tabs-default-color, var(--van-primary-color, #1989fa));
}

[data-theme='dark'] .child-tabs :deep(.van-tab),
.dark .child-tabs :deep(.van-tab) {
  color: rgba(255, 255, 255, 0.7);
}

[data-theme='dark'] .child-tabs :deep(.van-tab--active),
.dark .child-tabs :deep(.van-tab--active) {
  color: #fff;
}

[data-theme='dark'] .child-tab-name,
.dark .child-tab-name {
  color: inherit;
}

.summary-card {
  margin-top: 12px;
}

.balance-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.grant-btn {
  flex-shrink: 0;
  font-size: 11px;
  padding: 0 8px;
  height: 24px;
  border-radius: 12px;
}

.sheet-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}

.grant-field {
  margin-top: 8px;
  border-radius: 8px;
  background: var(--bg-secondary);
}

.grant-confirm-btn {
  margin-top: 16px;
  border-radius: 12px;
  background: var(--color-cost, #f5a623);
  border: none;
}

.content-tabs {
  margin-top: 12px;
}

.wish-list,
.chore-list {
  padding: 12px;
}

.wish-group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 16px 0 8px;
}

.wish-group-title:first-child {
  margin-top: 0;
}

.wish-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-elevated, 0 2px 8px rgba(1, 1, 32, 0.06));
  cursor: pointer;
}

.wish-card--fulfilled {
  opacity: 0.75;
}

.wish-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.wish-card-info {
  flex: 1;
  min-width: 0;
}

.wish-emoji-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.wish-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wish-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 4px;
}

.wish-cost {
  color: var(--color-cost, #f5a623);
  font-weight: 600;
}

.wish-cost--unset {
  color: var(--text-tertiary);
}

.wish-owner {
  color: var(--text-secondary);
  font-size: 12px;
}

.priority-icon {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
}

.priority-icon.high {
  background: var(--badge-high-bg, #ffe0e0);
  color: var(--badge-high-text, #c0392b);
}

.priority-icon.medium {
  background: var(--badge-medium-bg, #fff3cd);
  color: var(--badge-medium-text, #856404);
}

.priority-icon.low {
  background: var(--badge-low-bg, #e8f4fd);
  color: var(--badge-low-text, #1a6fa8);
}

.wish-desc-text {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 4px 0 0;
  line-height: 1.4;
}

.wish-rejection {
  font-size: 12px;
  color: var(--van-danger-color, #ee0a24);
  margin: 4px 0 0;
}

/* Wish detail bottom sheet */
.detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--separator);
}

.detail-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.detail-value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.detail-desc {
  padding: 8px 0;
}

.detail-desc-text {
  font-size: 14px;
  color: var(--text-primary);
  margin: 4px 0 0;
  line-height: 1.5;
  white-space: pre-wrap;
}

.detail-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.cost-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-secondary);
  border-radius: 10px;
  padding: 6px 14px;
  gap: 8px;
}

.cost-input-field {
  flex: 1;
  background: transparent;
  padding: 0;
}

.cost-label {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.btn-submit {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #4CAF50, #2E7D32);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-reject-confirm {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #ff5252, #d32f2f);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.btn-reject-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-realize-confirm {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #f9ca24, #f0932b);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.btn-realize-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-cancel {
  flex: 1;
  padding: 12px;
  border: 1px solid var(--separator);
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 15px;
  cursor: pointer;
}

.input {
  border: 1px solid var(--separator);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 15px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.error-msg {
  background: var(--error-bg, #f8d7da);
  color: var(--error-text, #721c24);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
}

.dialog-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.calendar-wrap {
  margin: 12px 16px 0;
}

/* Chore card styles — matches wish card layout */
.chore-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-elevated, 0 2px 8px rgba(1, 1, 32, 0.06));
}

.chore-card--completed {
  opacity: 0.75;
}

.chore-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.chore-card-info {
  flex: 1;
  min-width: 0;
}

.chore-emoji-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.chore-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chore-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.chore-assignee {
  color: var(--text-secondary);
  font-size: 12px;
}

.chore-reward-inline {
  color: var(--color-cost, #f5a623);
  font-weight: 600;
}

.chore-streak-icon {
  font-size: 11px;
  color: var(--van-warning-color, #ff976a);
}

/* Wish action buttons — pill style */
.wish-card .card-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  border-top: none;
}

.wish-card .action-btn {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  min-height: 40px;
  position: relative;
}

.wish-card .action-btn:active {
  transform: scale(0.97);
}

.wish-card .action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.wish-card .action-btn--success {
  color: #fff;
  background: linear-gradient(135deg, #4CAF50, #2E7D32);
}

.wish-card .action-btn--danger {
  color: #fff;
  background: linear-gradient(135deg, #ff5252, #d32f2f);
}

.wish-card .action-btn--muted {
  color: var(--text-secondary);
  background: var(--bg-secondary);
}

.wish-card .action-btn--primary {
  color: #fff;
  background: linear-gradient(135deg, #42A5F5, #1E88E5);
}

/* Chore card action buttons — pill style, matching wish cards */
.chore-card .card-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  border-top: none;
}

.chore-card .action-btn {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  min-height: 40px;
  position: relative;
}

.chore-card .action-btn:active {
  transform: scale(0.97);
}

.chore-card .action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.chore-card .action-btn--primary {
  color: #fff;
  background: linear-gradient(135deg, #42A5F5, #1E88E5);
}

.chore-card .action-btn--warning {
  color: #fff;
  background: linear-gradient(135deg, #ffb74d, #f57c00);
}

.chore-card .action-btn--danger {
  color: #fff;
  background: linear-gradient(135deg, #ff5252, #d32f2f);
}

.chore-card .action-btn--success {
  color: #fff;
  background: linear-gradient(135deg, #4CAF50, #2E7D32);
}

.chore-card .action-btn--muted {
  color: var(--text-secondary);
  background: var(--bg-secondary);
}

/* FAB */
.fab {
  position: fixed;
  right: 16px;
  bottom: 72px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--van-primary-color);
  color: var(--color-on-primary, #fff);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-elevated);
  z-index: 10;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
  border: none;
}

.fab:active {
  transform: scale(0.93);
  box-shadow: 0 2px 8px rgba(1, 1, 32, 0.2);
}

[data-theme='dark'] .fab {
  background: var(--color-lavender);
  color: #010120;
  box-shadow: 0 4px 16px rgba(189, 187, 255, 0.3);
}

/* Dark mode: content-tabs panel background */
[data-theme='dark'] .content-tabs :deep(.van-tabs__content),
.dark .content-tabs :deep(.van-tabs__content) {
  background: transparent;
}

[data-theme='dark'] .content-tabs :deep(.van-tab),
.dark .content-tabs :deep(.van-tab) {
  color: rgba(255, 255, 255, 0.7);
}

[data-theme='dark'] .content-tabs :deep(.van-tab--active),
.dark .content-tabs :deep(.van-tab--active) {
  color: #fff;
}
</style>