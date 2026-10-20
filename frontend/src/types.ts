export type Plane = 'axial' | 'coronal' | 'sagittal'
export type Labels = { left: string; right: string; top: string; bottom: string }
export type Scan = {
  session_id: string
  name: string
  synthetic: boolean
  metadata: { shape: [number, number, number]; spacing: [number, number, number]; units: string; orientation: [string, string, string]; affine: number[][]; dtype: string; intensity: [number, number] }
  orientation_labels: Record<Plane, Labels>
}
export type Measurement = { label: number; voxels: number; volume_ml: number }
export type Mask = { name: string; kind: 'reference' | 'annotation' | 'prediction'; labels: number[]; label_names: Record<string, string>; measurements: Measurement[] }
export type MeshData = { label: number; vertices: number[][]; faces: number[][] }
export type ForegroundCentre = { voxel: [number, number, number]; label: number | null }
export type VerifiedDemonstration = {
  case: string
  scope: string
  reference_verified: boolean
  reference_labels: number[]
  dice: { whole_tumour: number; tumour_core: number; enhancing_tumour: number }
  independent_validation: boolean
  limitation: string
  gpu: string
  inference_seconds: number
  peak_gpu_memory_gib: number
}

