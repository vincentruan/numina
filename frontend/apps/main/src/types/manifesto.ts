export interface Manifesto {
  id: string
  family_id: string
  current_version_id: string | null
  status: 'draft' | 'active' | 'archived'
  signing_deadline: string | null
  created_by: string
  created_at: string
  current_version: ManifestoVersion | null
  signatures: ManifestoSignature[]
  rejections: ManifestoRejection[]
}

export interface ManifestoVersion {
  id: string
  version_number: number
  template_id: string
  title: string
  body: string
  change_type: 'initial' | 'minor' | 'major'
  trackable_clause_indices: number[] | null
  signed_at: string | null
  created_by: string
  created_at: string
}

export interface ManifestoSignature {
  id: string
  user_id: string
  signature_data: string | null // null = tap-to-consent
  signed_at: string
}

export interface ManifestoRejection {
  id: string
  user_id: string
  reason: string | null
  created_at: string
}

export interface ManifestoDashboardSummary {
  manifesto_id: string | null
  title: string
  total_members: number
  signed_count: number
  status: string
}

export interface ManifestoFeedback {
  id: string
  user_id: string
  content: string
  is_read: boolean
  created_at: string
}

export interface ManifestoVersionHistoryItem {
  id: string
  version_number: number
  change_type: string
  title: string
  created_by: string
  created_at: string
}

export interface UnsignedManifestoCheck {
  has_unsigned: boolean
  manifesto_id: string | null
  title: string | null
}

import type { Component } from 'vue'

export interface TemplateDefinition {
  id: string
  nameKey: string
  lang: 'zh' | 'en'
  type: 'classic' | 'modern'
  component: Component
}

// ---------------------------------------------------------------------------
// Flow visualization types
// ---------------------------------------------------------------------------

export type FlowState = 'draft' | 'signing' | 'rejected' | 'modifying' | 'effective' | 'expired'

export type MemberSigningStatus =
  | 'signed'
  | 'confirmed'
  | 'pending_sign'
  | 'pending_confirm'
  | 'rejected'
  | 'expired'

export interface FlowMemberState {
  userId: string
  displayName: string
  role: 'owner' | 'member' | 'child'
  status: MemberSigningStatus
  isCurrentUser: boolean
  signatureData: string | null | undefined
  rejectionReason: string | null | undefined
  signedAt: string | null
  rejectedAt: string | null
}

export interface FlowDeadlineInfo {
  expired: boolean
  remaining: string | null
}

export interface FlowSigningProgress {
  signed: number
  total: number
}

export interface FlowCreatedNodeData {
  changeType: 'initial' | 'minor' | 'major'
  versionNumber: number
  creatorName: string
  createdAt: string
  dimmed?: boolean
}

export interface FlowPendingNodeData {
  deadline: string | null
  deadlineExpired: boolean
  dimmed?: boolean
}

export interface FlowVersionUpdateNodeData {
  updaterName: string
  currentVersion: number
  nextVersion: number
  dimmed?: boolean
}
