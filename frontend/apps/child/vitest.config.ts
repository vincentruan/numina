import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@numina/auth': path.resolve(__dirname, '../../packages/auth/src/index.ts'),
      '@numina/math': path.resolve(__dirname, '../../packages/math/src/index.ts'),
    },
    dedupe: ['vue', 'pinia'],
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['tests/setup.ts'],
    // Parallel execution for speed (Vitest 4 uses pool directly)
    pool: 'threads',
    minWorkers: 1,
    maxWorkers: 4,
    // Silent console in tests for machine-friendly output
    silent: true,
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/utils/*.ts', 'src/composables/*.ts'],
    },
  },
})
