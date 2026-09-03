import { ref, computed } from 'vue'
import { getChildManifesto, signChildManifesto } from '@/api/manifesto'
import { parseApiDate } from '@/utils/format'
import type { ChildManifestoData } from '@/api/manifesto'

export type AgeGroup = 'simple' | 'handwriting'

/**
 * Child manifesto signing composable.
 * Centralizes manifesto data fetch, signing, and age-branched UX.
 */
export function useManifestoSign(options?: { birthday?: string | null }) {
  const manifesto = ref<ChildManifestoData | null>(null)
  const loading = ref(true)
  const signed = ref(false)
  const celebrating = ref(false)

  // Age detection: birthday → age → branch
  // < 5 → 'simple' (tap-to-consent allowed)
  // >= 5 OR unknown → 'handwriting' (P1-1)
  const ageGroup = computed<AgeGroup>(() => {
    const birthday = options?.birthday
    if (!birthday) return 'handwriting'
    const birthDate = parseApiDate(birthday)
    if (Number.isNaN(birthDate.getTime())) return 'handwriting'
    const today = new Date()
    let age = today.getFullYear() - birthDate.getFullYear()
    const monthDiff = today.getMonth() - birthDate.getMonth()
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--
    }
    return age < 5 ? 'simple' : 'handwriting'
  })

  async function init() {
    loading.value = true
    try {
      const res = await getChildManifesto()
      manifesto.value = res.data
      signed.value = res.data.signed
    } catch {
      manifesto.value = null
    } finally {
      loading.value = false
    }
  }

  async function sign(signatureData: string | null) {
    await signChildManifesto(signatureData)
    signed.value = true
    if (manifesto.value) {
      manifesto.value = { ...manifesto.value, signed: true }
    }
    celebrating.value = true
  }

  function dismissCelebration() {
    celebrating.value = false
  }

  return {
    manifesto,
    loading,
    signed,
    celebrating,
    ageGroup,
    init,
    sign,
    dismissCelebration,
  }
}
