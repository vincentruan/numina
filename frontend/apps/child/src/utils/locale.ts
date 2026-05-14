import { ref, watchEffect } from 'vue'
import i18n from '@/i18n'

type Locale = 'zh-CN' | 'en-US'

function getStoredLocale(): Locale {
  const v = localStorage.getItem('child:locale')
  if (v === 'zh-CN' || v === 'en-US') return v
  return 'zh-CN'
}

const currentLocale = ref<Locale>(typeof window !== 'undefined' ? getStoredLocale() : 'zh-CN')

if (typeof window !== 'undefined') {
  watchEffect(() => {
    i18n.global.locale.value = currentLocale.value
    localStorage.setItem('child:locale', currentLocale.value)
  })
}

export function useLocale() {
  function setLocale(locale: Locale) {
    currentLocale.value = locale
  }
  return { currentLocale, setLocale }
}
