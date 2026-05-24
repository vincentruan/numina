import { ref, readonly, type Ref } from 'vue'

const QUERY = '(prefers-reduced-motion: reduce)'

let _mediaQuery: MediaQueryList | null = null
let _state: Ref<boolean> | null = null

function ensureState(): Ref<boolean> {
  if (_state) return _state
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    _state = ref(false)
    return _state
  }
  _mediaQuery = window.matchMedia(QUERY)
  _state = ref(_mediaQuery.matches)
  _mediaQuery.addEventListener('change', (e) => {
    if (_state) _state.value = e.matches
  })
  return _state
}

export function useReducedMotion(): Readonly<Ref<boolean>> {
  return readonly(ensureState())
}
