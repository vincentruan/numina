import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from '@vant/auto-import-resolver'

export default defineConfig({
  base: '/child/',
  plugins: [
    vue(),
    Components({
      resolvers: [VantResolver()]
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    },
    dedupe: ['vue', 'pinia']
  },
  server: {
    fs: {
      allow: ['../..']
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
