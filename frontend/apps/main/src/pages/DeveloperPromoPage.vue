<template>
  <div class="developer-promo-page" role="main" aria-label="开发者介绍">
    <!-- Hero: Deployment Complexity -->
    <section class="deploy-hero">
      <h1 class="hero-title">部署 Numina</h1>
      <p class="hero-subtitle">选择适合您的部署方式</p>

      <DeploymentHeatmap
        :options="deployOptions"
        :column-num="3"
      />
    </section>

    <!-- Terminal Animation -->
    <section class="terminal-section">
      <div class="terminal-block">
        <div class="terminal-header">
          <span class="terminal-title">Terminal</span>
        </div>
        <div class="terminal-body">
          <code class="terminal-command">
            docker-compose up -d<span class="cursor"></span>
          </code>
          <div class="terminal-output">
            <span class="output-line">[+] Running 3/3</span>
            <span class="output-line"> ✔ Container numina-backend  Started</span>
            <span class="output-line"> ✔ Container numina-frontend Started</span>
            <span class="output-line"> ✔ Container numina-nginx    Started</span>
          </div>
        </div>
      </div>
      <p class="terminal-tagline">一键启动，30秒就绪</p>
    </section>

    <!-- Quick Start Steps -->
    <section class="steps-section">
      <h2 class="section-title">快速开始</h2>

      <van-steps :active="0" class="deploy-steps">
        <van-step>克隆仓库</van-step>
        <van-step>配置环境</van-step>
        <van-step>启动服务</van-step>
        <van-step>访问应用</van-step>
      </van-steps>

      <div class="step-details">
        <van-collapse v-model="activeSteps">
          <van-collapse-item title="步骤 1: 克隆仓库" name="step1">
            <code class="step-code">git clone https://github.com/vincentruan/numina.git</code>
            <code class="step-code">cd numina</code>
          </van-collapse-item>
          <van-collapse-item title="步骤 2: 配置环境 (可选)" name="step2">
            <p>默认配置已可用。生产环境建议设置 SECRET_KEY。</p>
            <code class="step-code">export SECRET_KEY="your-secret-key"</code>
          </van-collapse-item>
          <van-collapse-item title="步骤 3: 启动服务" name="step3">
            <code class="step-code">docker-compose up -d</code>
            <p>服务将在 http://localhost:8080 启动</p>
          </van-collapse-item>
          <van-collapse-item title="步骤 4: 访问应用" name="step4">
            <p>浏览器打开 http://localhost:8080</p>
            <p>创建家庭账户，开始追踪资产</p>
          </van-collapse-item>
        </van-collapse>
      </div>
    </section>

    <!-- Architecture -->
    <section class="architecture-section">
      <h2 class="section-title">技术架构</h2>

      <div class="architecture-diagram">
        <div class="arch-layer frontend">
          <span class="layer-name">Frontend</span>
          <span class="layer-tech">Vue 3 + Vite + Vant 4</span>
        </div>
        <div class="arch-layer backend">
          <span class="layer-name">Backend</span>
          <span class="layer-tech">FastAPI + SQLAlchemy</span>
        </div>
        <div class="arch-layer database">
          <span class="layer-name">Database</span>
          <span class="layer-tech">SQLite / MySQL / PostgreSQL</span>
        </div>
        <div class="arch-layer nginx">
          <span class="layer-name">Nginx</span>
          <span class="layer-tech">Reverse Proxy</span>
        </div>
      </div>

      <p class="arch-note">
        自托管设计 · 所有组件运行在您的硬件上 · 无外部依赖
      </p>
    </section>

    <!-- Trust Badges -->
    <section class="trust-section">
      <h2 class="section-title">项目质量</h2>

      <van-grid :column-num="2" class="trust-grid">
        <van-grid-item>
          <div class="badge-content">
            <span class="badge-value">36+</span>
            <span class="badge-label">自动化测试</span>
            <a href="https://github.com/vincentruan/numina/actions" target="_blank" class="badge-link">
              CI 运行状态 →
            </a>
          </div>
        </van-grid-item>
        <van-grid-item>
          <div class="badge-content">
            <span class="badge-value">MIT</span>
            <span class="badge-label">开源许可</span>
            <a href="https://github.com/vincentruan/numina/blob/main/LICENSE" target="_blank" class="badge-link">
              查看许可 →
            </a>
          </div>
        </van-grid-item>
        <van-grid-item>
          <div class="badge-content">
            <span class="badge-value">Docker</span>
            <span class="badge-label">容器化部署</span>
            <span class="badge-note">Compose 一键启动</span>
          </div>
        </van-grid-item>
        <van-grid-item>
          <div class="badge-content">
            <span class="badge-value">开源</span>
            <span class="badge-label">可审计代码</span>
            <a href="https://github.com/vincentruan/numina" target="_blank" class="badge-link">
              查看源码 →
            </a>
          </div>
        </van-grid-item>
      </van-grid>
    </section>

    <!-- CTA -->
    <section class="cta-section">
      <van-button type="primary" size="large" round class="cta-button">
        <a href="https://github.com/vincentruan/numina" target="_blank">
          查看源码
        </a>
      </van-button>
      <router-link to="/promo/family" class="cta-alt">
        ← 家庭用户介绍
      </router-link>
    </section>

    <!-- Footer -->
    <footer class="promo-footer">
      <router-link to="/welcome">← 返回首页</router-link>
      <span class="divider">|</span>
      <a href="https://github.com/vincentruan/numina/tree/main/docs" target="_blank">文档</a>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import DeploymentHeatmap from '@/components/promotional/DeploymentHeatmap.vue'

const activeSteps = ref<string[]>([])

const deployOptions = [
  { method: 'Docker Compose', time: '10 分钟', difficulty: 'easy' as const },
  { method: '手动部署', time: '30 分钟', difficulty: 'medium' as const },
  { method: '云服务器', time: '2 小时', difficulty: 'hard' as const }
]
</script>

<style scoped>
.developer-promo-page {
  min-height: 100vh;
  background: #1d1d1f;
  color: #f5f5f7;
}

/* Hero */
.deploy-hero {
  padding: 64px 16px 48px;
  text-align: center;
}

.hero-title {
  font-size: 36px;
  font-weight: 700;
  color: #f5f5f7;
  margin: 0 0 8px;
}

.hero-subtitle {
  font-size: 16px;
  color: rgba(245, 245, 247, 0.7);
  margin: 0 0 32px;
}

/* Terminal */
.terminal-section {
  padding: 48px 16px;
  background: #2d2d2f;
  text-align: center;
}

.terminal-block {
  max-width: 500px;
  margin: 0 auto;
  background: #1d1d1f;
  border-radius: 12px;
  overflow: hidden;
}

.terminal-header {
  background: #3d3d3f;
  padding: 8px 12px;
}

.terminal-title {
  font-size: 12px;
  color: rgba(245, 245, 247, 0.5);
}

.terminal-body {
  padding: 16px;
}

.terminal-command {
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: 16px;
  color: #f5f5f7;
  display: block;
}

.terminal-output {
  margin-top: 16px;
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: 12px;
}

.output-line {
  display: block;
  color: rgba(245, 245, 247, 0.6);
}

/* Blinking cursor */
.cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  background: #f5f5f7;
  margin-left: 4px;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .cursor {
    animation: none;
    opacity: 1;
  }
}

.terminal-tagline {
  margin-top: 16px;
  font-size: 14px;
  color: rgba(245, 245, 247, 0.7);
}

/* Steps */
.steps-section {
  padding: 48px 16px;
}

.section-title {
  font-size: 24px;
  font-weight: 600;
  color: #f5f5f7;
  margin: 0 0 24px;
  text-align: center;
}

.deploy-steps {
  margin-bottom: 24px;
}

.step-details {
  background: #2d2d2f;
  border-radius: 12px;
}

.step-code {
  display: block;
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: 14px;
  color: #f5f5f7;
  background: #1d1d1f;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 8px 0;
}

/* Architecture */
.architecture-section {
  padding: 48px 16px;
  background: #2d2d2f;
}

.architecture-diagram {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 400px;
  margin: 0 auto 16px;
}

.arch-layer {
  background: rgba(245, 245, 247, 0.1);
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.layer-name {
  font-weight: 600;
  color: #f5f5f7;
}

.layer-tech {
  font-size: 12px;
  color: rgba(245, 245, 247, 0.6);
}

.arch-note {
  text-align: center;
  font-size: 14px;
  color: rgba(245, 245, 247, 0.7);
}

/* Trust */
.trust-section {
  padding: 48px 16px;
}

.trust-grid {
  background: #2d2d2f;
  border-radius: 12px;
}

.badge-content {
  padding: 16px;
  text-align: center;
}

.badge-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: var(--color-action-blue);
}

.badge-label {
  display: block;
  font-size: 14px;
  color: rgba(245, 245, 247, 0.7);
  margin-top: 4px;
}

.badge-note {
  display: block;
  font-size: 12px;
  color: rgba(245, 245, 247, 0.5);
  margin-top: 4px;
}

.badge-link {
  display: inline-block;
  font-size: 12px;
  color: var(--color-action-blue);
  margin-top: 8px;
}

/* CTA */
.cta-section {
  padding: 48px 16px;
  text-align: center;
}

.cta-button {
  width: 100%;
  max-width: 300px;
}

.cta-button a {
  color: inherit;
  text-decoration: none;
}

.cta-alt {
  display: inline-block;
  margin-top: 16px;
  color: rgba(245, 245, 247, 0.7);
  font-size: 14px;
}

/* Footer */
.promo-footer {
  padding: 24px 16px;
  text-align: center;
  border-top: 1px solid rgba(245, 245, 247, 0.1);
}

.promo-footer a {
  color: rgba(245, 245, 247, 0.7);
  font-size: 14px;
}

.divider {
  color: rgba(245, 245, 247, 0.3);
  margin: 0 12px;
}

/* Desktop */
@media (min-width: 768px) {
  .hero-title {
    font-size: 48px;
  }

  .terminal-block {
    max-width: 600px;
  }

  .architecture-diagram {
    max-width: 500px;
  }

  .section-title {
    font-size: 28px;
  }
}
</style>