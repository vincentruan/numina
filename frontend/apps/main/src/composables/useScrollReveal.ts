import { onMounted, onBeforeUnmount, type Ref } from 'vue'

const REVEALED_CLASS = 'revealed'
const REVEAL_SELECTOR = '[data-reveal]'

/**
 * Observes `[data-reveal]` elements within a container and adds a `revealed`
 * class when they enter the viewport (one-shot, no reset).
 *
 * Respects `prefers-reduced-motion`: when reduce is preferred, the observer
 * is not created — elements remain visible via the CSS safety net in style.css.
 *
 * Assumption: template components are synchronously imported, so child DOM
 * is present at parent onMounted per Vue 3 lifecycle. If templates become
 * async in the future, add a MutationObserver or watch to re-query.
 */
export function useScrollReveal(container: Ref<HTMLElement | null>) {
  let observer: IntersectionObserver | null = null

  function prefersReducedMotion(): boolean {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  }

  onMounted(() => {
    if (prefersReducedMotion()) return

    const el = container.value
    if (!el) return

    const targets = el.querySelectorAll(REVEAL_SELECTOR)
    if (targets.length === 0) return

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add(REVEALED_CLASS)
            observer!.unobserve(entry.target)
          }
        }
      },
      {
        threshold: 0.1,
        rootMargin: '0px 0px -10% 0px',
      },
    )

    targets.forEach((target) => observer!.observe(target))
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })
}
