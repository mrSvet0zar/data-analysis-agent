const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function startAnalysis(file, requestText) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('request_text', requestText)

  const res = await fetch(`${API_URL}/api/analyze`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `Upload failed (${res.status})`)
  }
  return res.json()
}

export function openJobSocket(jobId) {
  const wsUrl = API_URL.replace(/^http/, 'ws')
  return new WebSocket(`${wsUrl}/ws/job/${jobId}`)
}

export { API_URL }
