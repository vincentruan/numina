---
date: 2026-04-18
topic: landing-page-design
focus: Static landing page design for Numina family asset visualization app
mode: elsewhere-software
---

# Ideation: Numina Landing Page Design

## Topic Context

**Product:** Numina — 隐私优先、自托管的家庭资产可视化管理系统 (Family Asset Visualization)

**Target Audience:** Privacy-conscious families, self-hosting enthusiasts, parents with children

**Constraints:** Pure static page (no backend), nginx served, showcase features and highlights

**Prior Art & External Context:**
- Proton (Swiss privacy, shields/locks visuals), Bitwarden (trust badges, open-source)
- YNAB (emotional value prop), fintech deep blues, compliance badges lift conversions 10-20%
- 2026 trends: Product-first heroes, dark themes with bright accents, micro-interactions
- Cross-domain: Kids+parents dual-audience design, IoT/Home Assistant aesthetic for self-hosters

## Ranked Ideas

### 1. Terminal Hero + Smart Home Dashboard IoT
**Description:** Hero section is a stylized terminal displaying `docker-compose up -d` with blinking cursor. Landing page aesthetic mimics smart home dashboard (Home Assistant style) — assets displayed as "connected devices" on family network, dark theme with accent colors. Docker deploy becomes "Install Your Home Finance Hub." Product screenshots shown in "connected device" card format.

**Rationale:** Perfect audience alignment. Self-hosting enthusiasts already run Home Assistant/Plex — IoT dashboard aesthetic signals "local network, no cloud." Terminal hero removes marketing fluff and proves one-command promise. Pure static: terminal is CSS animation, device cards are styled screenshots.

**Downsides:** Terminal aesthetic may feel "too technical" for non-technical family users. Need secondary family-friendly entry path.

**Confidence:** 95%

**Complexity:** Medium

**Status:** Explored

### 2. Trust Vault + Privacy Contract
**Description:** Hero displays 3D vault illustration (CSS/Lottie) that lives in user's home — visual metaphor for self-hosting. Vault animates open on scroll. Below hero, "Privacy Contract" block lists verifiable claims: "Data never leaves your server," "No third-party analytics," "No cloud sync unless configured." Each claim links to documentation proof. CTA: "Build Your Family's Vault."

**Rationale:** Vault makes self-hosting emotionally concrete — families protect valuables in safes. Privacy Contract moves from marketing fluff to verifiable claims. Both pure static: vault animation, styled text block.

**Downsides:** Vault illustration requires design asset creation.

**Confidence:** 90%

**Complexity:** Medium

**Status:** Unexplored

### 3. Family Quest Map + Star Coin Animation
**Description:** Landing framed as family adventure. Hero shows RPG-style map with "territories" (asset categories). Scroll reveals "quest achievements" unlocking features. Children star coin system highlighted with animated GIF/Lottie: chore → coin drops → progress fills. CTA: "Start Your Family's Quest." Dual-audience: parents see "family project," kids see "family game."

**Rationale:** Unique gamification extends Numina's existing star coin system to landing. RPG metaphor novel for fintech, creates emotional engagement, dual-audience. Star coin animation is viral hook. Pure static: map illustration, GIF/Lottie animation.

**Downsides:** Adventure metaphor may not resonate with serious finance users.

**Confidence:** 85%

**Complexity:** Medium

**Status:** Unexplored

### 4. Feature Comparison Grid (SEO Asset)
**Description:** Structured comparison table: Numina vs Mint vs YNAB vs spreadsheet. Rows: Privacy, Family Structure, Liability Tracking, Children Incentives, Deploy Complexity. Semantic HTML for SEO. Below grid: "Why families choose Numina" summary.

**Rationale:** Highest leverage — one grid becomes SEO traffic source, comparison content, documentation structure, competitor positioning. Attracts "YNAB alternative" and "self-hosted finance" searches. Pure static: HTML table.

**Downsides:** Competitor data may become outdated.

**Confidence:** 90%

**Complexity:** Low

**Status:** Unexplored

### 5. Compound Trust Badge Chain
**Description:** Row of trust badges with expansion: "389 Tests ✓" → hover reveals test categories → click links to CI. "Self-Hosted ✓" → hover shows "no cloud dependency" → click links to architecture docs. "Open Source ✓" → hover shows repo link → click opens GitHub. CSS hover + anchor links (static).

**Rationale:** Proven pattern (Bitwarden, Proton). Compound expansion creates trust depth. Leverages existing assets: 389 tests, CI, GitHub. Pure static: CSS hover, anchor links. High reuse: badges reusable in README, docs, changelog.

**Downsides:** Hover doesn't work on mobile — need tap alternative.

**Confidence:** 85%

**Complexity:** Low

**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Deploy in 60 Seconds Interactive Demo | Requires backend — violates pure static constraint |
| 2 | Family Adoption Simulator | Too complex for static; requires interactive simulation |
| 3 | Dashboard-Only Landing (interactive) | Interactive dashboard violates pure static constraint |
| 4 | Live Preview Sandbox | localStorage demo requires significant JS complexity |
| 5 | Feature Playground Hero (interactive tabs) | Interactive toggle violates pure static spirit |
| 6 | 30-Second Deploy Countdown (live) | Backend required for live countdown simulation |
| 7 | Metric Carousel with Live Sources | Backend/API calls required — not static |
| 8 | Live Deployment Counter | Backend required for counter simulation |
| 9 | Before Numina Stories | Too negative/fear-based; may alienate users |
| 10 | Abstract Asset Visualization | Too abstract; users need visual product proof |
| 11 | Typography-Driven Narrative (zero visuals) | Extreme; fintech needs visual trust signals |
| 12 | Kids-Only Target Page | Main audience is deploying parents |
| 13 | Numina Encyclopedia (10x longer) | Information overload; loses landing purpose |
| 14 | No Tech Terms Family Story | Tech audience expects tech terms |
| 15 | Family Garden Metaphor | Metaphor unrelated to actual product UI |
| 16 | Financial Health Checkup Medical | Metaphor mismatch; Numina isn't health/medical |
| 17 | Family Cookbook Recipe | Metaphor stretch; finance ≠ cooking |
| 18 | Museum Collection Curatorial | Disconnected from actual product aesthetic |
| 19 | Outcome Journey Story | Feature sections more practical for evaluation |
| 20 | Educational Gateway (mini-course) | Adds friction before conversion |
| 21 | Mobile-Native Scroll (thumb-first) | Not novel; responsive covers this |
| 22 | Prosperity Narrative (red/gold) | May not match modern fintech aesthetic |
| 23 | Family Portal Dual-Audience | Complex split-screen; simpler dual focus possible |
| 24 | Dark Theme Toggle Preview | Low novelty; just a standard toggle |
| 25 | Privacy Visual Language (motifs everywhere) | Overlaps with stronger Trust Vault concept |
| 26 | Star Coin Incentive Demo Loop (interactive) | Interactive animation violates static constraint |
| 27 | Privacy Laboratory (interactive trace) | Interactive hover/tap violates static spirit |
| 28 | Family Tree Demo as Onboarding | Requires interactive form simulation |
| 29 | Spreadsheet vs Numina Comparison | Covered by Feature Comparison Grid |
| 30 | Mobile-First Proof Hero | Phone mockup is standard — not novel |
| 31 | No Lock-in Export Promise | Feature-level; trust badges cover this |
| 32 | What We Don't Do Grid | Covered by Privacy Contract |
| 33 | Social Proof Carousel | Covered by Trust Dashboard/badges |
| 34 | Feature-First Grid No Hero | Hero adds value; grid is secondary |

## Session Log
- 2026-04-18: Phase 1 grounding (context synthesis, learnings search, web research)
- 2026-04-18: Phase 2 ideation — 6 frames, 48 raw ideas + 5 combinations = 53 candidates
- 2026-04-18: Phase 3 adversarial filtering — 35 rejected, 5 survivors
- 2026-04-18: Phase 6 user selected brainstorm for idea #1 (Terminal Hero + Smart Home IoT)