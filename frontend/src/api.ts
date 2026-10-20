import type { ForegroundCentre, InferenceAvailability, InferenceJob, Mask, MeshData, Plane, Scan, VerifiedDemonstration } from './types'

async function checked<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || 'Request failed')
  }
  return response.json() as Promise<T>
}

export async function createSession() { return checked<{session_id: string}>(await fetch('/api/sessions', { method: 'POST' })) }
export async function clearSession(id: string) { return checked<{cleared: boolean}>(await fetch(`/api/sessions/${id}`, { method: 'DELETE' })) }
export async function loadSynthetic(id: string) { return checked<{scan: Scan; mask: Mask}>(await fetch(`/api/sessions/${id}/synthetic`, { method: 'POST' })) }
export async function loadVerifiedDemonstration(id: string) { return checked<{scan: Scan; mask: Mask; demonstration: VerifiedDemonstration}>(await fetch(`/api/sessions/${id}/verified-demonstration`, { method: 'POST' })) }
export async function uploadScan(id: string, file: File) {
  const body = new FormData(); body.append('file', file)
  return checked<Scan>(await fetch(`/api/sessions/${id}/scan`, { method: 'POST', body }))
}
export async function uploadMask(id: string, file: File, kind: 'reference' | 'annotation' | 'prediction') {
  const body = new FormData(); body.append('file', file); body.append('kind', kind)
  return checked<Mask>(await fetch(`/api/sessions/${id}/mask`, { method: 'POST', body }))
}
export function sliceUrl(id: string, plane: Plane, index: number, window: number, level: number, opacity: number, labels: number[]) {
  const params = new URLSearchParams({ window: String(window), level: String(level), opacity: String(opacity), labels: labels.join(',') })
  return `/api/sessions/${id}/slice/${plane}/${index}?${params}`
}
export async function getMesh(id: string, label: number) { return checked<MeshData>(await fetch(`/api/sessions/${id}/mesh/${label}`)) }
export async function getForegroundCentre(id: string, label?: number) { return checked<ForegroundCentre>(await fetch(`/api/sessions/${id}/mask/foreground-centre${label ? `?label=${label}` : ''}`)) }
export async function getInferenceAvailability() { return checked<InferenceAvailability>(await fetch('/api/inference/status')) }
export async function submitInference(id: string, files: Record<'t1c'|'t1'|'t2'|'flair', File>) {
  const body = new FormData(); (['t1c','t1','t2','flair'] as const).forEach(name => body.append(name, files[name]))
  return checked<InferenceJob>(await fetch(`/api/sessions/${id}/inference`, { method: 'POST', body }))
}
export async function getInferenceJob(id: string) { return checked<InferenceJob>(await fetch(`/api/sessions/${id}/inference`)) }

