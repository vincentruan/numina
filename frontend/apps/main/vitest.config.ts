import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'happy-dom',
    setupFiles: ['tests/setup.ts'],
    // Use forks pool for better memory isolation (each test file in separate process)
    // Threads pool shares memory across workers, causing OOM with large test suites
    pool: 'forks',
    minWorkers: 1,
    maxWorkers: 2,
    // Silent console in tests for machine-friendly output
    silent: true,
    deps: {
      inline: [/packages\/auth/, 'nprogress'],
    },
    include: [
      'tests/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}',
      'src/**/__tests__/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/utils/*.ts', 'src/composables/*.ts'],
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@numina/math': fileURLToPath(new URL('../../packages/math/src/index.ts', import.meta.url)),
    },
  },
})