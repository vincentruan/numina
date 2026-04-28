import http from './index'

export interface WebAuthnOptionsResponse {
  options: Record<string, unknown>
  challenge: string
}

export async function getRegistrationOptions(childId: string): Promise<WebAuthnOptionsResponse> {
  const { data } = await http.post<WebAuthnOptionsResponse>('/auth/child/webauthn/register-options', {
    child_id: childId,
  })
  return data
}

export async function submitRegistration(
  childId: string,
  credential: Record<string, unknown>,
  challenge: string,
): Promise<{ message: string }> {
  const { data } = await http.post<{ message: string }>('/auth/child/webauthn/register', {
    child_id: childId,
    credential,
    challenge,
  })
  return data
}

export async function getAuthenticationOptions(childId: string): Promise<WebAuthnOptionsResponse> {
  const { data } = await http.post<WebAuthnOptionsResponse>('/auth/child/webauthn/login-options', {
    child_id: childId,
  })
  return data
}

export async function authenticateWithPasskey(
  childId: string,
  credential: Record<string, unknown>,
  challenge: string,
): Promise<{ access_token: string; refresh_token: string; token_type: string }> {
  const { data } = await http.post<{
    access_token: string
    refresh_token: string
    token_type: string
  }>('/auth/child/webauthn/login', {
    child_id: childId,
    credential,
    challenge,
  })
  return data
}
