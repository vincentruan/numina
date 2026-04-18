<template>
  <div class="family-promo-page" role="main" aria-label="家庭用户介绍">
    <!-- Privacy Hero -->
    <section class="privacy-hero">
      <van-notice-bar
        background="rgba(255,255,255,0.1)"
        color="#fff"
        left-icon="shield-o"
        scrollable
        class="privacy-banner"
      >
        数据在你手中 · 隐私优先 · 本地存储 · 无云端上传
      </van-notice-bar>

      <div class="hero-content">
        <h1 class="hero-title">数据在你手中</h1>
        <p class="hero-subtitle">家庭资产可视化管理，隐私第一</p>

        <div class="data-flow">
          <div class="flow-node">🏠 您的家庭</div>
          <div class="flow-arrow">→</div>
          <div class="flow-node local">💻 本地服务器</div>
          <div class="flow-arrow">→</div>
          <div class="flow-node secure">🔒 安全存储</div>
        </div>

        <p class="flow-note">数据永不离开您的硬件</p>
      </div>
    </section>

    <!-- Trust Badges -->
    <section class="trust-section">
      <h2 class="section-title">为什么选择 Numina</h2>

      <van-collapse v-model="activeBadges" class="trust-badges">
        <van-collapse-item title="无账号注册追踪" name="tracking">
          <p>无需手机号、邮箱注册。家庭成员通过邀请码加入，不关联外部身份。</p>
        </van-collapse-item>
        <van-collapse-item title="本地数据库" name="database">
          <p>所有资产数据存储在您的设备上，SQLite 数据库，您完全掌控。</p>
        </van-collapse-item>
        <van-collapse-item title="开源审计" name="opensource">
          <p>代码完全开源 (MIT License)，任何人可审计安全性和隐私保护机制。</p>
          <a href="https://github.com/vincentruan/numina" target="_blank" class="badge-link">
            查看源码 →
          </a>
        </van-collapse-item>
      </van-collapse>
    </section>

    <!-- Feature Screenshots -->
    <section class="screenshots-section">
      <h2 class="section-title">一目了然的家庭财务</h2>
      <ScreenshotGallery
        :screenshots="screenshots"
        :autoplay="true"
        :interval="4000"
      />
    </section>

    <!-- Value Story -->
    <section class="story-section">
      <h2 class="section-title">想象张阿姨的家庭</h2>
      <div class="story-card">
        <p class="story-text">
          张阿姨有三套房产、两辆车、股票基金投资，还有房贷车贷。
          以前每到年底，她要翻遍所有银行APP、保险单、购房合同才能算清净资产。
        </p>
        <p class="story-text">
          用了 Numina 后，所有资产一目了然。<br>
          净资产趋势图清晰可见。<br>
          孩子的心愿可以用星星硬币激励完成家务。<br>
          三代人的资产，一个应用全掌握。
        </p>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta-section">
      <van-button type="primary" size="large" round to="/register" class="cta-button">
        开始守护家庭财富
      </van-button>
      <p class="cta-note">30秒创建家庭，立即开始追踪</p>
    </section>

    <!-- Footer -->
    <footer class="promo-footer">
      <router-link to="/welcome">← 返回首页</router-link>
      <router-link to="/promo/developer">技术部署指南</router-link>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ScreenshotGallery from '@/components/promotional/ScreenshotGallery.vue'

const activeBadges = ref<string[]>([])

// Screenshots from landing/assets (copied during build)
const screenshots = [
  '/landing/assets/dashboard-final-top.webp',
  '/landing/assets/dashboard-final-cards.webp',
  '/landing/assets/wishes-page.webp'
]
</script>

<style scoped>
.family-promo-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #667eea 0%, #f5f5f7 40%);
}

/* Privacy Hero */
.privacy-hero {
  padding: 32px 16px;
  text-align: center;
}

.privacy-banner {
  margin-bottom: 24px;
  border-radius: 8px;
}

.hero-content {
  max-width: 400px;
  margin: 0 auto;
}

.hero-title {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 8px;
}

.hero-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.85);
  margin: 0 0 32px;
}

.data-flow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.flow-node {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  color: #fff;
}

.flow-node.local {
  background: rgba(0, 122, 255, 0.3);
}

.flow-node.secure {
  background: rgba(52, 199, 89, 0.3);
}

.flow-arrow {
  color: rgba(255, 255, 255, 0.6);
  font-size: 20px;
}

.flow-note {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

/* Trust Section */
.trust-section {
  padding: 48px 16px;
  background: #f5f5f7;
}

.section-title {
  font-size: 24px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0 0 24px;
  text-align: center;
}

.trust-badges {
  background: #fff;
  border-radius: 12px;
}

.badge-link {
  display: inline-block;
  margin-top: 8px;
  color: #007aff;
  font-size: 14px;
}

/* Screenshots */
.screenshots-section {
  padding: 48px 16px;
  background: #fff;
}

/* Story */
.story-section {
  padding: 48px 16px;
  background: #f5f5f7;
}

.story-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  max-width: 500px;
  margin: 0 auto;
}

.story-text {
  font-size: 16px;
  color: #1d1d1f;
  line-height: 1.6;
  margin: 0 0 16px;
}

.story-text:last-child {
  margin-bottom: 0;
}

/* CTA */
.cta-section {
  padding: 48px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  text-align: center;
}

.cta-button {
  width: 100%;
  max-width: 300px;
}

.cta-note {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 12px;
}

/* Footer */
.promo-footer {
  padding: 24px 16px;
  background: #fff;
  text-align: center;
  display: flex;
  gap: 24px;
  justify-content: center;
}

.promo-footer a {
  color: #007aff;
  font-size: 14px;
}

/* Desktop */
@media (min-width: 768px) {
  .hero-title {
    font-size: 40px;
  }

  .section-title {
    font-size: 28px;
  }

  .story-text {
    font-size: 18px;
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .privacy-banner {
    scrollable: false;
  }
}
</style>