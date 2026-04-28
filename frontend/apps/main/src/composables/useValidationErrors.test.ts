import { describe, it, expect } from 'vitest'
import { useValidationErrors } from './useValidationErrors'

describe('useValidationErrors', () => {
  it('setErrors populates map from 422 details', () => {
    const { validationErrors, setErrors } = useValidationErrors()
    setErrors({
      response: {
        status: 422,
        data: {
          details: [
            { field: 'username', code: 'REQUIRED', msg: '此字段为必填项' },
            { field: 'password', code: 'TOO_SHORT', msg: '长度至少 6 位' },
          ],
        },
      },
    })
    expect(validationErrors.value['username']).toEqual({ code: 'REQUIRED', msg: '此字段为必填项' })
    expect(validationErrors.value['password']).toEqual({ code: 'TOO_SHORT', msg: '长度至少 6 位' })
  })

  it('setErrors is no-op for non-422 errors', () => {
    const { validationErrors, setErrors } = useValidationErrors()
    setErrors({ response: { status: 500, data: {} } })
    expect(validationErrors.value).toEqual({})
  })

  it('setErrors is no-op when details is missing', () => {
    const { validationErrors, setErrors } = useValidationErrors()
    setErrors({ response: { status: 422, data: { message: 'error' } } })
    expect(validationErrors.value).toEqual({})
  })

  it('setErrors is no-op for non-error values', () => {
    const { validationErrors, setErrors } = useValidationErrors()
    setErrors(null)
    setErrors(undefined)
    setErrors('string error')
    expect(validationErrors.value).toEqual({})
  })

  it('clearErrors resets to empty', () => {
    const { validationErrors, setErrors, clearErrors } = useValidationErrors()
    setErrors({
      response: {
        status: 422,
        data: { details: [{ field: 'name', code: 'REQUIRED', msg: 'required' }] },
      },
    })
    expect(Object.keys(validationErrors.value).length).toBe(1)
    clearErrors()
    expect(validationErrors.value).toEqual({})
  })

  it('getError returns correct entry for known field', () => {
    const { setErrors, getError } = useValidationErrors()
    setErrors({
      response: {
        status: 422,
        data: { details: [{ field: 'password', code: 'TOO_SHORT', msg: '长度至少 6 位' }] },
      },
    })
    expect(getError('password')).toEqual({ code: 'TOO_SHORT', msg: '长度至少 6 位' })
  })

  it('getError returns undefined for unknown field', () => {
    const { getError } = useValidationErrors()
    expect(getError('nonexistent')).toBeUndefined()
  })
})
