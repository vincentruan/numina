import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
  server: {
    port: 5175,
    strictPort: true,
  },
  build: {
    // Capacitor loads the built assets from the native project's
    // `app/src/main/assets/public/` directory (copied by `cap sync`).
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
