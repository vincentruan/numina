import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from '@vant/auto-import-resolver'
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons-ng'
import { VitePWA } from 'vite-plugin-pwa'

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
    }),
    VitePWA({
      registerType: 'prompt',
      injectRegister: false,
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      manifest: {
        name: 'Numina Kids',
        short_name: 'Numina Kids',
        theme_color: '#e8b94a',
        background_color: '#fffaf0',
        display: 'standalone',
        start_url: '/child/',
        scope: '/child/',
        icons: [
          { src: '/child/pwa-icon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,ico,svg,png,woff2}'],
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024, // 5 MiB — exceeds default 2 MiB
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src')
    },
    dedupe: ['vue', 'pinia', '@vue/runtime-dom', '@vue/runtime-core', 'vue-i18n', '@intlify/core-base', '@intlify/shared', 'vant', '@vant/use']
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
