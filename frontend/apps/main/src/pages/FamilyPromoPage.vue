<template>
  <div class="family-promo-page" role="main" :aria-label="t('familyPromo.ariaLabel')">
    <!-- Privacy Hero -->
    <section class="privacy-hero">
      <van-notice-bar
        background="rgba(255,255,255,0.1)"
        color="#fff"
        left-icon="shield-o"
        scrollable
        class="privacy-banner"
      >
        {{ t('familyPromo.privacyBanner') }}
      </van-notice-bar>

      <div class="hero-content">
        <h1 class="hero-title">{{ t('familyPromo.heroTitle') }}</h1>
        <p class="hero-subtitle">{{ t('familyPromo.heroSubtitle') }}</p>

        <div class="data-flow">
          <div class="flow-node">{{ t('familyPromo.flowNodeHome') }}</div>
          <div class="flow-arrow">→</div>
          <div class="flow-node local">{{ t('familyPromo.flowNodeLocal') }}</div>
          <div class="flow-arrow">→</div>
          <div class="flow-node secure">{{ t('familyPromo.flowNodeSecure') }}</div>
        </div>

        <p class="flow-note">{{ t('familyPromo.flowNote') }}</p>
      </div>
    </section>

    <!-- Trust Badges -->
    <section class="trust-section">
      <h2 class="section-title">{{ t('familyPromo.sectionWhy') }}</h2>

      <van-collapse v-model="activeBadges" class="trust-badges">
        <van-collapse-item :title="t('familyPromo.badgeTracking')" name="tracking">
          <p>{{ t('familyPromo.badgeTrackingDesc') }}</p>
        </van-collapse-item>
        <van-collapse-item :title="t('familyPromo.badgeDatabase')" name="database">
          <p>{{ t('familyPromo.badgeDatabaseDesc') }}</p>
        </van-collapse-item>
        <van-collapse-item :title="t('familyPromo.badgeOpensource')" name="opensource">
          <p>{{ t('familyPromo.badgeOpensourceDesc') }}</p>
          <a href="https://github.com/vincentruan/numina" target="_blank" class="badge-link">
            {{ t('familyPromo.viewSource') }}
          </a>
        </van-collapse-item>
      </van-collapse>
    </section>

    <!-- Feature Screenshots -->
    <section class="screenshots-section">
      <h2 class="section-title">{{ t('familyPromo.sectionFeatures') }}</h2>
      <ScreenshotGallery
        :screenshots="screenshots"
        :autoplay="true"
        :interval="4000"
      />
    </section>

    <!-- Value Story -->
    <section class="story-section">
      <h2 class="section-title">{{ t('familyPromo.storyTitle') }}</h2>
      <div class="story-card">
        <p class="story-text">
          {{ t('familyPromo.storyText1') }}
        </p>
        <p class="story-text">
          {{ t('familyPromo.storyText2') }}
        </p>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta-section">
      <van-button type="primary" size="large" round to="/register" class="cta-button">
        {{ t('familyPromo.ctaButton') }}
      </van-button>
      <p class="cta-note">{{ t('familyPromo.ctaNote') }}</p>
    </section>

    <!-- Footer -->
    <footer class="promo-footer">
      <router-link to="/welcome">{{ t('familyPromo.backToWelcome') }}</router-link>
      <router-link to="/promo/developer">{{ t('familyPromo.devGuide') }}</router-link>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ScreenshotGallery from '@/components/promotional/ScreenshotGallery.vue'

const { t } = useI18n()
const activeBadges = ref<string[]>([])

// Screenshots from landing/assets (copied during build)
const screenshots = [
  '/landing/assets/dashboard-final-top.webp',
  '/landing/assets/dashboard-final-cards.webp',
  '/landing/assets/wishes-page.webp'
]
</script>