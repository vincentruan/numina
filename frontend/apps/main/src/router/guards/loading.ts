import type { Router } from 'vue-router'
import { useLoadingOverlay } from '@numina/auth'

/**
 * Setup router guards for automatic loading state during navigation
 * - beforeEach: show loading when route changes start
 * - afterEach: hide loading when route changes complete
 */
export function setupLoadingGuards(router: Router) {
  const { increment, decrement } = useLoadingOverlay()

  router.beforeEach(() => {
    increment()
    return true
  })

  router.afterEach(() => {
    decrement()
  })
}
