import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

export const uploadPDF = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
  })
}

export const listDocuments = () => api.get('/documents').then(r => r.data.documents)

export const sendChat = (payload) => api.post('/chat', payload).then(r => r.data)

export const clearSession = (sessionId) => api.delete(`/session/${sessionId}`)

export const runEval = (payload) => api.post('/evaluate', payload).then(r => r.data)

export const healthCheck = () => api.get('/health').then(r => r.data)
