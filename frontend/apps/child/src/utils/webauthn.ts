/**
 * WebAuthn (Passkey) browser API utilities.
 *
 * Wraps navigator.credentials for passkey registration and authentication.
 * Used by ChildAuthPage for biometric login with PIN fallback.
 */

export interface WebAuthnSupport {
  supported: boolean
  reason?: string
}

/**
 * Check if the current browser supports WebAuthn.
 */
export function checkWebAuthnSupport(): WebAuthnSupport {
  if (typeof window === 'undefined') {
    return { supported: false, reason: 'Not in browser environment' }
  }
  if (!window.PublicKeyCredential) {
    return { supported: false, reason: 'WebAuthn not supported in this browser' }
  }
  return { supported: true }
}

/**
 * Convert a base64url string to ArrayBuffer.
 * Returns a plain ArrayBuffer to satisfy BufferSource type constraint.
 */
export function base64urlToArrayBuffer(base64url: string): ArrayBuffer {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
  const binary = atob(padded)
  const buffer = new ArrayBuffer(binary.length)
  const bytes = new Uint8Array(buffer)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return buffer
}

/**
 * Convert a base64url string to Uint8Array.
 */
export function base64urlToUint8Array(base64url: string): Uint8Array {
  return new Uint8Array(base64urlToArrayBuffer(base64url))
}

/**
 * Convert ArrayBuffer or Uint8Array to base64url string.
 */
export function uint8ArrayToBase64url(buffer: ArrayBuffer | Uint8Array): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

/**
 * Prepare registration options from server response for navigator.credentials.create().
 * Converts base64url-encoded fields to ArrayBuffer as required by the browser API.
 */
function prepareRegistrationOptions(
  options: Record<string, unknown>,
): PublicKeyCredentialCreationOptions {
  const challenge = base64urlToArrayBuffer(options.challenge as string)
  const userId = base64urlToArrayBuffer((options.user as Record<string, string>).id)

  const excludeCredentials = ((options.excludeCredentials as Array<Record<string, string>>) ?? []).map(
    (cred) => ({
      id: base64urlToArrayBuffer(cred.id),
      type: 'public-key' as const,
    }),
  )

  return {
    ...(options as unknown as PublicKeyCredentialCreationOptions),
    challenge,
    user: {
      ...(options.user as PublicKeyCredentialUserEntity),
      id: userId,
    },
    excludeCredentials,
  }
}

/**
 * Prepare authentication options from server response for navigator.credentials.get().
 * Converts base64url-encoded fields to ArrayBuffer as required by the browser API.
 */
function prepareAuthenticationOptions(
  options: Record<string, unknown>,
): PublicKeyCredentialRequestOptions {
  const challenge = base64urlToArrayBuffer(options.challenge as string)

  const allowCredentials = ((options.allowCredentials as Array<Record<string, string>>) ?? []).map(
    (cred) => ({
      id: base64urlToArrayBuffer(cred.id),
      type: 'public-key' as const,
    }),
  )

  return {
    ...(options as unknown as PublicKeyCredentialRequestOptions),
    challenge,
    allowCredentials,
  }
}

/**
 * Serialize a PublicKeyCredential to a plain object for sending to the server.
 */
function serializeCredential(credential: PublicKeyCredential): Record<string, unknown> {
  const response = credential.response

  if (response instanceof AuthenticatorAttestationResponse) {
    return {
      id: credential.id,
      rawId: uint8ArrayToBase64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: uint8ArrayToBase64url(response.clientDataJSON),
        attestationObject: uint8ArrayToBase64url(response.attestationObject),
      },
    }
  }

  if (response instanceof AuthenticatorAssertionResponse) {
    return {
      id: credential.id,
      rawId: uint8ArrayToBase64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: uint8ArrayToBase64url(response.clientDataJSON),
        authenticatorData: uint8ArrayToBase64url(response.authenticatorData),
        signature: uint8ArrayToBase64url(response.signature),
        userHandle: response.userHandle ? uint8ArrayToBase64url(response.userHandle) : null,
      },
    }
  }

  throw new Error('Unknown credential response type')
}

/**
 * Register a new passkey for the current device.
 *
 * @param options - Registration options from server (POST /auth/child/webauthn/register-options)
 * @returns Serialized credential to send to server (POST /auth/child/webauthn/register)
 * @throws Error if user cancels or browser rejects
 */
export async function registerPasskey(
  options: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const preparedOptions = prepareRegistrationOptions(options)
  const credential = await navigator.credentials.create({
    publicKey: preparedOptions,
  })
  if (!credential || !(credential instanceof PublicKeyCredential)) {
    throw new Error('No credential returned from browser')
  }
  return serializeCredential(credential)
}

/**
 * Authenticate using an existing passkey.
 *
 * @param options - Authentication options from server (POST /auth/child/webauthn/login-options)
 * @returns Serialized credential to send to server (POST /auth/child/webauthn/login)
 * @throws Error if user cancels or browser rejects
 */
export async function authenticatePasskey(
  options: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const preparedOptions = prepareAuthenticationOptions(options)
  const credential = await navigator.credentials.get({
    publicKey: preparedOptions,
  })
  if (!credential || !(credential instanceof PublicKeyCredential)) {
    throw new Error('No credential returned from browser')
  }
  return serializeCredential(credential)
}
