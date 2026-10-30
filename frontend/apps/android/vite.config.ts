import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import { readFileSync } from 'node:fs'

const pkg = JSON.parse(readFileSync(path.resolve(import.meta.dirname, 'package.json'), 'utf-8'))

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
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
