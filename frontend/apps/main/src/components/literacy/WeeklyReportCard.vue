<template>
  <div class="weekly-report-card">
    <!-- Badge Status -->
    <ReportSection :title="t('literacyReport.badgeStatus')" icon="medal-o">
      <div v-if="report.report_json.badge_summary.new_unlocks.length > 0" class="sub-block">
        <div class="sub-label">{{ t('literacyReport.newUnlocks') }}</div>
        <div class="badge-list">
          <van-tag
            v-for="(badge, i) in report.report_json.badge_summary.new_unlocks"
            :key="`unlock-${i}`"
            type="primary"
            size="medium"
            round
            class="badge-tag"
          >
            {{ badge }}
          </van-tag>
        </div>
      </div>
      <div v-if="report.report_json.badge_summary.progress.length > 0" class="sub-block">
        <div class="sub-label">{{ t('literacyReport.progress') }}</div>
        <ul class="highlight-list">
          <li v-for="(item, i) in report.report_json.badge_summary.progress" :key="`prog-${i}`">
            {{ item }}
          </li>
        </ul>
      </div>
      <div
        v-if="report.report_json.badge_summary.new_unlocks.length === 0 && report.report_json.badge_summary.progress.length === 0"
        class="empty-hint"
      >
        --
      </div>
    </ReportSection>

    <!-- Behavioral Highlights -->
    <ReportSection :title="t('literacyReport.behavioralHighlights')" icon="fire-o">
      <ul v-if="report.report_json.behavioral_highlights.length > 0" class="highlight-list">
        <li
          v-for="(item, i) in report.report_json.behavioral_highlights"
          :key="`hl-${i}`"
        >
          {{ item }}
        </li>
      </ul>
      <div v-else class="empty-hint">--</div>
    </ReportSection>

    <!-- Scenario Analysis -->
    <ReportSection :title="t('literacyReport.scenarioAnalysis')" icon="question-o">
      <div class="scenario-block">
        <div class="scenario-row">
          <span class="scenario-label">{{ t('literacyReport.childChoice') }}</span>
          <span class="scenario-value">{{ report.report_json.scenario_analysis.choice }}</span>
        </div>
        <div class="scenario-row">
          <span class="scenario-label">{{ t('literacyReport.interpretation') }}</span>
          <span class="scenario-value">{{ report.report_json.scenario_analysis.interpretation }}</span>
        </div>
      </div>
    </ReportSection>

    <!-- Family Activity -->
    <ReportSection :title="t('literacyReport.familyActivity')" icon="friends-o">
      <div v-if="report.report_json.family_activity" class="activity-callout">
        <MarkdownContent :content="String(report.report_json.family_activity)" />
      </div>
      <div v-else class="empty-hint">--</div>
    </ReportSection>

    <!-- Narrative -->
    <div v-if="report.narrative" class="narrative-block">
      <MarkdownContent :content="report.narrative" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { WeeklyReportResponse } from '@/api/literacy'
import ReportSection from './ReportSection.vue'
import MarkdownContent from '@/components/ai-chat/MarkdownContent.vue'

const { t } = useI18n()

defineProps<{
  report: WeeklyReportResponse
}>()
</script>

<style scoped>
.weekly-report-card {
  padding: 4px 0;
  font-family: Inter, sans-serif;
}

.sub-block {
  margin-bottom: 8px;
}

.sub-block:last-child {
  margin-bottom: 0;
}

.sub-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.badge-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.badge-tag {
  font-size: 12px;
}

.highlight-list {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.8;
}

.highlight-list li::marker {
  color: var(--van-primary-color);
}

.scenario-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scenario-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.scenario-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.scenario-value {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
}

.narrative-block {
  margin: 12px 16px;
  padding: 12px;
  background: var(--card-bg, #f5f5ff);
  border-radius: 8px;
}

.activity-callout {
  background: rgba(var(--van-primary-color-rgb, 57, 122, 255), 0.08);
  border-radius: 8px;
  padding: 10px 12px;
  line-height: 1.6;
}

.empty-hint {
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
