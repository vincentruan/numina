import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from '@vant/auto-import-resolver'
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons-ng'

export default defineConfig({
  base: '/child/',
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
    port: 5174,
    strictPort: true,
    fs: {
      allow: [
        path.resolve(import.meta.dirname, '../..'),
        // pnpm symlink resolves to real path in root node_modules/.pnpm
        path.resolve(import.meta.dirname, '../../../node_modules/.pnpm'),
      ]
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
