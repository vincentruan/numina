---
date: 2026-04-18
topic: frontend-promotional-pages
focus: Two static promotional pages within Vue frontend module (family + developer)
mode: repo-grounded
---

# Ideation: Numina Frontend Promotional Pages

## Grounding Context

**Codebase Context:**
- Numina: privacy-first, self-hosted family asset visualization (Vue 3 + TypeScript + Vite + Vant 4)
- Frontend structure: Guest routes (login/register) outside MainLayout — promotional pages follow same pattern
- Screenshots exist in `tests/*.png` + seed data `seed-complete-data.sh` for realistic demo
- Chinese UI text throughout, currency CNY

**Prior Art:**
- Supabase: "For developers" / "For enterprise" tabs swap content
- Fortnite season pass: visual rewards (casual) + math breakdown (hardcore)
- Zillow: "Find dream home" (buyer) vs "Grow business" (agent) dual entry
- MyChart: patient summary + expandable clinical details

**Key Insight:** Prior landing page ideation had scope drift (GitHub Pages instead of frontend module). This run corrects scope: pages must be Vue components within frontend/src/pages/, routes in frontend/src/router/.

## Ranked Survivors

### 1. Dual-Path Landing Gateway
**Description:** Single entry route `/welcome` with two portal buttons: "守护家庭财富" (family) and "技术部署指南" (developer). Each leads to dedicated promotional page. Mobile viewport defaults to family; desktop shows both equally. Guest route pattern matches login/register.

**Rationale:** Matches two-page requirement exactly. Validated by Zillow/Supabase patterns. Eliminates wrong-audience friction at first touchpoint.

**Downsides:** Requires router configuration change. Family users may not realize two paths exist.

**Confidence:** 95%

**Complexity:** Medium

**Status:** Explored

---

### 2. Privacy Trust Showcase (Chinese-First Family Page)
**Description:** Family page opens with "数据在你手中" (Data in Your Hands) privacy declaration. Visual data flow diagram: family → local server → no cloud. Concrete guarantees: "无账号注册追踪", "本地数据库", "开源审计". Followed by family narrative story.

**Rationale:** Family users' primary objection is privacy fear. Chinese-first content matches project identity. Privacy-first positioning unifies both audiences.

**Downsides:** Visual diagram requires design asset. Story narrative needs copywriting.

**Confidence:** 90%

**Complexity:** Medium

**Status:** Unexplored

---

### 3. Deployment Complexity Heatmap (Developer Page)
**Description:** Developer page includes deployment difficulty matrix: Docker (10 min, green), Manual (30 min, yellow), Cloud (2 hr, red). Color-coded heatmap with time estimates. Animated terminal showing `docker-compose up -d` execution.

**Rationale:** Developers need instant feasibility assessment. Heatmap answers "how hard?" in 5 seconds. Terminal animation provides visceral proof.

**Downsides:** Heatmap visual needs design. Terminal animation requires CSS keyframes.

**Confidence:** 85%

**Complexity:** Low

**Status:** Unexplored

---

### 4. Reusable Promotional Component Library
**Description:** Extract Vue components: `TrustBadge.vue`, `FeatureGrid.vue`, `ComparisonTable.vue`, `ScreenshotGallery.vue`. Accept `audience` prop to toggle messaging. Compounds into: promotional pages, onboarding tooltips, dashboard help, feature announcements.

**Rationale:** Component investment compounds value. Trust badges relevant to both audiences. Feature grid auto-populates from 21 system categories.

**Downsides:** Requires architecture decision. Comparison table needs competitor research.

**Confidence:** 90%

**Complexity:** Medium

**Status:** Unexplored

---

### 5. Outcome vs Process Visual Strategy
**Description:** Family page = outcome (dashboard screenshots, wealth charts). Developer page = process (architecture diagrams, Docker steps, deployment flowcharts). No overlap. Screenshots from tests/take-screenshots.js.

**Rationale:** Family users care about "what will we see?" Developers care about "how to deploy?" Fortnite pattern validates outcome/process split.

**Downsides:** Architecture diagrams may need creation.

**Confidence:** 90%

**Complexity:** Low

**Status:** Unexplored

---

### 6. Audience-Specific Trust Signals
**Description:** Family page = Chinese testimonials ("三代人资产"). Developer page = technical badges (GitHub stars, CI passing, MIT license). Trust signals match audience expectations.

**Rationale:** MyChart pattern validates: testimonials for patients, badges for clinicians. MIT license exists. GitHub Actions has 36+ tests.

**Downsides:** Testimonials need sourcing (placeholder acceptable).

**Confidence:** 85%

**Complexity:** Low

**Status:** Unexplored

---

### 7. WeChat QR Code Family Referral
**Description:** "分享给家人" button generates QR code with invite code + promotional URL. Client-side generation via `qrcode` library. Bridges offline family gatherings → digital app.

**Rationale:** Chinese family sharing via WeChat — QR code is native format. Viral distribution mechanism.

**Downsides:** Requires npm dependency. May need placeholder for non-family visitors.

**Confidence:** 80%

**Complexity:** Low

**Status:** Unexplored

---

## Additional Ideas (Phase 2 Extended)

### Chinese Localization Frame
1. **Multi-Generational Messaging (三代同堂)** — Grandparents can view grandchildren wish progress
2. **WeChat QR Code Integration** — Replace text invite code with QR for WeChat sharing
3. **Chinese Privacy Sovereignty (数据主权)** — PIPL compliance framing, "国产替代" positioning
4. **财商教育 Badge** — Financial literacy education certification appeal to Chinese parents
5. **家账 Metaphor** — Rebrand from "资产可视化" to traditional "家账" (family ledger)
6. **开源 Badge Enhancement** — Add Gitee mirror link, GitHub stars display
7. **Chinese Holiday Features** — 春节盘点, seasonal messaging based on date
8. **Financial Terminology Expansion** — Use Chinese-native terms: 理财, 房贷车贷, 家底

### Vue/Vant Implementation Frame
1. **Feature Tour Carousel (van-swipe)** — Swipeable feature screenshots with auto-play
2. **Trust Badges (van-collapse)** — Accordion badges with built-in animation
3. **Demo Dashboard Preview** — ECharts with mock data, no API calls
4. **Animated Terminal (CSS Keyframes)** — Typing effect with scoped CSS
5. **Comparison Grid (van-grid)** — Responsive columns, touch-optimized
6. **Feature Cards (van-popup)** — Bottom popup for expanded details
7. **Privacy Banner (van-notice-bar)** — Scrollable privacy commitment
8. **Quick Start Wizard (van-steps)** — Step-by-step deploy guide

### Conversion Optimization Frame
1. **Sticky CTA Banner** — "One-command deploy" copy button, progress indicator
2. **Family Trust Carousel** — Anonymized testimonials with blurred screenshots
3. **Privacy Hero Diagram** — Animated network diagram: Your Home → Numina Server
4. **Bounce Recovery Modal** — Exit-intent with "forgotten assets" statistic
5. **Scroll-to-Action Hierarchy** — Problem → Solution → Proof → CTA structure
6. **Developer Sandbox Preview** — Interactive terminal simulation, Codespaces link
7. **Live Metrics Counter** — "Join X families tracking ¥Y million"
8. **Analytics Hooks** — Intersection observer for section engagement tracking

---

## Rejection Summary

| Count | Reason |
|-------|--------|
| 41 | Scope contradictions — ideas proposing README-only, login integration, single page, or external deployment instead of two frontend Vue pages |
| 12 | Beyond static scope — require backend sessions, interactive demos, or external services |

---

## Session Log
- 2026-04-18: Phase 1 grounding (frontend scan, learnings, web research)
- 2026-04-18: Phase 2 ideation — 6 frames → 48 raw + 5 combinations → 53 candidates
- 2026-04-18: Phase 2 extended — 3 additional frames → 24 more candidates
- 2026-04-18: Phase 3 adversarial filtering — 41 rejected, 7 survivors + 24 additional