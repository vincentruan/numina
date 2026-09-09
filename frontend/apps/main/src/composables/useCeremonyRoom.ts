import { onMounted, onBeforeUnmount } from 'vue'

const CEREMONY_CLASS = 'ceremony-mode'

/**
 * Coordinates the ceremony-mode body class for the Ceremonial Chamber.
 * Adds `ceremony-mode` to <body> on mount (dims the layout tab bar),
 * removes it on unmount. Returns a close() handler bound to router.back().
 *
 * Covers R1 (nav-bar replaced by close button), R4 (tab bar stays visible),
 * R9 (CSS-variable-driven, no hardcoded colors).
 */
export function useCeremonyRoom(routerBack: () => void) {
  onMounted(() => {
    document.body.classList.add(CEREMONY_CLASS)
  })

  onBeforeUnmount(() => {
    document.body.classList.remove(CEREMONY_CLASS)
  })

  function close() {
    document.body.classList.remove(CEREMONY_CLASS)
    routerBack()
  }

  return { close }
}
