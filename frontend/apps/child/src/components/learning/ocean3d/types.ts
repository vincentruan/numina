/** Minimal structural shape shared by ocean picking, framing and navigation. */
export interface OceanCameraNode {
  id: string
  x: number
  z: number
  worldRadius: number
}

/** Camera framing accepts a node without the navigation id. */
export type OceanCameraTarget = Omit<OceanCameraNode, 'id'>

/** Node reference emitted with navigation events and accepted by the page. */
export interface OceanNodeRef extends OceanCameraNode {
  subject?: string
}

/** Build the composite id used by global L1 domain tiles. */
export function composeDomainId(subject: string, domain: string): string {
  return `${subject}:${domain}`
}

/** Read a domain id that may be composite or already bare; unknown subjects are left alone. */
export function parseDomainId(id: string, subject: string): string {
  const prefix = `${subject}:`
  return id.startsWith(prefix) ? id.slice(prefix.length) : id
}
