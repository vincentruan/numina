import { ref, type InjectionKey, type Ref } from 'vue'

export interface ValidationError {
  code: string
  msg: string
}

export interface UseValidationErrors {
  validationErrors: Ref<Record<string, ValidationError>>
  setErrors: (axiosError: unknown) => void
  clearErrors: () => void
  getError: (field: string) => ValidationError | undefined
}

export const validationErrorsKey: InjectionKey<UseValidationErrors> = Symbol('validationErrors')

export function useValidationErrors(): UseValidationErrors {
  const validationErrors = ref<Record<string, ValidationError>>({})

  function setErrors(axiosError: unknown): void {
    const err = axiosError as { response?: { status?: number; data?: { details?: Array<{ field: string; code: string; msg: string }> } } }
    if (err?.response?.status !== 422) return
    const details = err.response?.data?.details
    if (!Array.isArray(details)) return
    const map: Record<string, ValidationError> = {}
    for (const item of details) {
      if (item.field) {
        map[item.field] = { code: item.code, msg: item.msg }
      }
    }
    validationErrors.value = map
  }

  function clearErrors(): void {
    validationErrors.value = {}
  }

  function getError(field: string): ValidationError | undefined {
    return validationErrors.value[field]
  }

  return { validationErrors, setErrors, clearErrors, getError }
}
