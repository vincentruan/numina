<template>
  <div class="welcome-page" role="main" aria-label="欢迎">
    <div class="welcome-content">
      <header class="welcome-header">
        <h1 class="welcome-title">Numina</h1>
        <p class="welcome-subtitle">家庭资产一目了然</p>
      </header>

      <div class="portal-buttons">
        <router-link
          to="/promo/family"
          class="portal-card family-card"
          aria-label="家庭用户入口"
        >
          <div class="card-icon">🏠</div>
          <h2 class="card-title">守护家庭财富</h2>
          <p class="card-desc">隐私优先，数据在您手中</p>
          <van-button type="primary" size="large" class="card-button">
            了解更多
          </van-button>
        </router-link>

        <router-link
          to="/promo/developer"
          class="portal-card developer-card"
          aria-label="开发者入口"
        >
          <div class="card-icon">⚡</div>
          <h2 class="card-title">技术部署指南</h2>
          <p class="card-desc">一键部署，30秒就绪</p>
          <van-button type="default" size="large" class="card-button">
            查看文档
          </van-button>
        </router-link>
      </div>

      <footer class="welcome-footer">
        <p class="footer-text">
          已有家庭账户？
          <router-link to="/login">直接登录</router-link>
        </p>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
// Pure static page - no logic needed
</script>

<style scoped>
.welcome-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
}

.welcome-content {
  width: 100%;
  max-width: 600px;
}

.welcome-header {
  text-align: center;
  margin-bottom: 48px;
}

.welcome-title {
  font-size: 48px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  letter-spacing: 4px;
}

.welcome-subtitle {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.85);
  margin-top: 12px;
}

.portal-buttons {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.portal-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 32px 24px;
  text-decoration: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  transition: transform 150ms ease, box-shadow 150ms ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.portal-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.portal-card:focus {
  outline: 2px solid #007aff;
  outline-offset: 2px;
}

/* Family card - primary (larger on mobile) */
.family-card {
  min-height: 200px;
}

.card-icon {
  font-size: 48px;
  line-height: 1;
}

.card-title {
  font-size: 24px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.card-desc {
  font-size: 14px;
  color: #6e6e73;
  margin: 0;
}

.card-button {
  width: 100%;
  margin-top: 8px;
}

.welcome-footer {
  margin-top: 32px;
  text-align: center;
}

.footer-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}

.footer-text a {
  color: #fff;
  text-decoration: underline;
}

/* Desktop: equal dual layout */
@media (min-width: 768px) {
  .portal-buttons {
    flex-direction: row;
  }

  .portal-card {
    flex: 1;
    min-height: 240px;
  }

  .family-card,
  .developer-card {
    /* Equal size on desktop */
  }

  .welcome-title {
    font-size: 56px;
  }

  .welcome-subtitle {
    font-size: 20px;
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .portal-card {
    transition: none;
  }

  .portal-card:hover {
    transform: none;
  }
}
</style>