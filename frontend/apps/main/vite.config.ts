import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from '@vant/auto-import-resolver'
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons-ng'

export default defineConfig({
  base: '/',
  plugins: [
    vue(),
    Components({
      resolvers: [VantResolver()]
    }),
    createSvgIconsPlugin({
      iconDirs: [path.resolve(import.meta.dirname, 'src/icons/svg')],
      symbolId: 'icon-[name]',
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src')
    },
    dedupe: ['vue', 'pinia', '@vue/runtime-dom', '@vue/runtime-core', 'vue-i18n', '@intlify/core-base', '@intlify/shared']
  },
  server: {
    port: 5173,
    strictPort: true,
    fs: {
      allow: [
        path.resolve(import.meta.dirname, '../..'),
        // pnpm symlink resolves to real path in root node_modules/.pnpm
        path.resolve(import.meta.dirname, '../../../node_modules/.pnpm'),
      ]
    },
    proxy: {
      '/api/threads': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        // SSE streaming needs long timeout — LLM tool-calling / thinking can
        // exceed the default node HTTP agent timeout and silently drop the
        // connection (symptom: "Send failed" after long loading).
        timeout: 10 * 60 * 1000,
        proxyTimeout: 10 * 60 * 1000,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Same SSE concern for backend streaming endpoints (/ai/chat/stream,
        // /ai/report/ws, etc.). Non-streaming requests are unaffected.
        timeout: 10 * 60 * 1000,
        proxyTimeout: 10 * 60 * 1000,
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
