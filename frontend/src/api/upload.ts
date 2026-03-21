import http from './index'

export interface UploadResponse {
  url: string
}

export function uploadImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return http.post<UploadResponse>('/upload/image', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}