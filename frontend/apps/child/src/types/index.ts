// Child app types
// Shared auth types re-exported from @numina/auth
export type { User, ChildUser } from '@numina/auth'

// Family type (used by family store)
export interface Family {
  id: string
  name: string
  custom_title?: string
  invite_code: string
  creator_code?: string
  created_by: string
  members: import('@numina/auth').User[]
}
