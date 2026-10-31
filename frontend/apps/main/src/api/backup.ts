import http from './index'

export interface BackupRun {
  backup_run_id: string | null
  backup_date: string
  file_path: string
  file_size: number | null
  status: string
  trigger_type: string
  created_at: string
}

export interface BackupListResponse {
  items: BackupRun[]
}

export interface BackupCreated {
  backup_run_id: string
  backup_date: string
  file_path: string
  file_size: number
}

export interface RestorePreview {
  delete: Record<string, number>
  insert: Record<string, number>
  backup_date: string
  export_version: string
}

export const BACKUP_PATH_PREFIX = '/import'

export function listBackups(params: { limit?: number; offset?: number } = {}) {
  return http.get<BackupListResponse>(`${BACKUP_PATH_PREFIX}/backups`, { params })
}

export function triggerBackup() {
  return http.post<BackupCreated>(`${BACKUP_PATH_PREFIX}/backup`)
}

export function previewRestore(payload: {
  backup_run_id?: string
  backup_date?: string
}) {
  return http.post<RestorePreview>(`${BACKUP_PATH_PREFIX}/restore?dry_run=true`, payload)
}

export function executeRestore(payload: {
  backup_run_id?: string
  backup_date?: string
}) {
  return http.post(`${BACKUP_PATH_PREFIX}/restore`, payload)
}

export function restoreFiles() {
  return http.post<{ task_id: string }>(`${BACKUP_PATH_PREFIX}/restore-files`)
}

export function getRestoreProgress(taskId: string) {
  return http.get<{
    status: 'running' | 'completed' | 'failed' | 'partial_success'
    files_completed: number
    files_total: number
    files_failed: number
  }>(`${BACKUP_PATH_PREFIX}/restore-files/${taskId}`)
}
