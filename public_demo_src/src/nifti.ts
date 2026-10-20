import * as nifti from 'nifti-reader-js'

const MIB = 1024 * 1024
export const MAX_FILE_BYTES = 256 * MIB
export const MAX_DECOMPRESSED_BYTES = 768 * MIB
export const MAX_VOXELS = 150_000_000

export type Affine = [number[], number[], number[], number[]]

export type VolumeData = {
  name: string
  shape: [number, number, number]
  affine: Affine
  spacingMm: [number, number, number]
  orientation: [string, string, string]
  values: Float32Array
  voxelVolumeMl: number
}

const TYPE_READERS: Record<number, [number, (view: DataView, offset: number, little: boolean) => number]> = {
  2: [1, (v, o) => v.getUint8(o)],
  4: [2, (v, o, l) => v.getInt16(o, l)],
  8: [4, (v, o, l) => v.getInt32(o, l)],
  16: [4, (v, o, l) => v.getFloat32(o, l)],
  64: [8, (v, o, l) => v.getFloat64(o, l)],
  256: [1, (v, o) => v.getInt8(o)],
  512: [2, (v, o, l) => v.getUint16(o, l)],
  768: [4, (v, o, l) => v.getUint32(o, l)],
}

function determinant3(matrix: number[][]) {
  const [a, b, c] = matrix
  return a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
}

function orientationFromAffine(affine: Affine): [string, string, string] {
  const positive = ['R', 'A', 'S']
  const negative = ['L', 'P', 'I']
  const used = new Set<number>()
  return [0, 1, 2].map(column => {
    const candidates = [0, 1, 2].sort((a, b) => Math.abs(affine[b][column]) - Math.abs(affine[a][column]))
    const row = candidates.find(candidate => !used.has(candidate)) ?? candidates[0]
    used.add(row)
    return affine[row][column] >= 0 ? positive[row] : negative[row]
  }) as [string, string, string]
}

function unitScaleToMm(code: number) {
  const spatial = code & 7
  if (spatial === 1) return 1000
  if (spatial === 2) return 1
  if (spatial === 3) return 0.001
  throw new Error('Spatial units are missing or unsupported. Use a NIfTI file declared in metres, millimetres, or microns.')
}

export async function readNiftiFile(file: File): Promise<VolumeData> {
  const lower = file.name.toLowerCase()
  if (!(lower.endsWith('.nii') || lower.endsWith('.nii.gz'))) throw new Error('Choose a .nii or .nii.gz file.')
  if (!file.size) throw new Error('The selected file is empty.')
  if (file.size > MAX_FILE_BYTES) throw new Error(`File exceeds the ${MAX_FILE_BYTES / MIB} MiB browser limit.`)

  let bytes = await file.arrayBuffer()
  if (nifti.isCompressed(bytes)) bytes = await nifti.decompressAsync(bytes)
  if (bytes.byteLength > MAX_DECOMPRESSED_BYTES) throw new Error(`Decompressed NIfTI exceeds the ${MAX_DECOMPRESSED_BYTES / MIB} MiB browser limit.`)
  if (!nifti.isNIFTI(bytes)) throw new Error('The file is not a valid single-file NIfTI-1 or NIfTI-2 image.')

  const header = nifti.readHeader(bytes)
  const dims = header.dims.map(Number)
  if (dims[0] !== 3 || dims.slice(1, 4).some(value => !Number.isInteger(value) || value <= 0)) {
    throw new Error('Only one 3D NIfTI volume is supported; 4D or invalid dimensions cannot be loaded.')
  }
  const shape = dims.slice(1, 4) as [number, number, number]
  const voxelCount = shape[0] * shape[1] * shape[2]
  if (!Number.isSafeInteger(voxelCount) || voxelCount > MAX_VOXELS) throw new Error(`Volume exceeds the ${MAX_VOXELS.toLocaleString()} voxel browser limit.`)

  const reader = TYPE_READERS[header.datatypeCode]
  if (!reader) throw new Error(`NIfTI datatype code ${header.datatypeCode} is not supported for browser viewing.`)
  const image = nifti.readImage(header, bytes)
  const [bytesPerVoxel, read] = reader
  if (image.byteLength < voxelCount * bytesPerVoxel) throw new Error('The NIfTI voxel payload is truncated.')
  const view = new DataView(image)
  const slope = Number(header.scl_slope) || 1
  const intercept = Number(header.scl_inter) || 0
  const values = new Float32Array(voxelCount)
  for (let index = 0; index < voxelCount; index++) {
    const value = read(view, index * bytesPerVoxel, header.littleEndian) * slope + intercept
    if (!Number.isFinite(value)) throw new Error(`Voxel data contains a non-finite value at index ${index.toLocaleString()}.`)
    values[index] = value
  }

  const unitScale = unitScaleToMm(Number(header.xyzt_units))
  const rawAffine = header.affine
  if (!rawAffine || rawAffine.length !== 4 || rawAffine.some(row => row.length !== 4 || row.some(value => !Number.isFinite(value)))) {
    throw new Error('The NIfTI header does not contain a finite 4 × 4 affine.')
  }
  const affine = rawAffine.map((row, rowIndex) => row.map((value, column) => rowIndex < 3 && column < 4 ? value * unitScale : value)) as Affine
  const linear = affine.slice(0, 3).map(row => row.slice(0, 3))
  const determinant = determinant3(linear)
  if (!Number.isFinite(determinant) || Math.abs(determinant) < 1e-9) throw new Error('The NIfTI affine is singular, so physical geometry cannot be determined.')
  const spacingMm = [0, 1, 2].map(column => Math.hypot(affine[0][column], affine[1][column], affine[2][column])) as [number, number, number]
  if (spacingMm.some(value => !Number.isFinite(value) || value <= 0)) throw new Error('The NIfTI affine contains invalid voxel spacing.')

  return {
    name: file.name,
    shape,
    affine,
    spacingMm,
    orientation: orientationFromAffine(affine),
    values,
    voxelVolumeMl: Math.abs(determinant) / 1000,
  }
}

export function assertCompatible(scan: VolumeData, mask: VolumeData) {
  if (scan.shape.some((value, index) => value !== mask.shape[index])) {
    throw new Error(`Mask dimensions ${mask.shape.join(' × ')} do not match scan dimensions ${scan.shape.join(' × ')}.`)
  }
  let largestDifference = 0
  for (let row = 0; row < 4; row++) for (let column = 0; column < 4; column++) {
    largestDifference = Math.max(largestDifference, Math.abs(scan.affine[row][column] - mask.affine[row][column]))
  }
  if (largestDifference > 0.001) throw new Error(`Mask affine differs from the scan by up to ${largestDifference.toFixed(4)} mm (allowed: 0.001 mm).`)
}

export function validateMask(volume: VolumeData) {
  const labels = new Set<number>()
  for (let index = 0; index < volume.values.length; index++) {
    const value = volume.values[index]
    const rounded = Math.round(value)
    if (Math.abs(value - rounded) > 1e-5 || rounded < 0 || rounded > 65535) {
      throw new Error(`Mask voxels must be non-negative integer labels; found ${value} at index ${index.toLocaleString()}.`)
    }
    if (rounded) labels.add(rounded)
    if (labels.size > 32) throw new Error('Mask contains more than 32 foreground labels; simplify it before browser rendering.')
  }
  if (!labels.size) throw new Error('Mask has no foreground labels.')
  return [...labels].sort((a, b) => a - b)
}

export function affinePoint(affine: Affine, x: number, y: number, z: number): [number, number, number] {
  return [0, 1, 2].map(row => affine[row][0] * x + affine[row][1] * y + affine[row][2] * z + affine[row][3]) as [number, number, number]
}
