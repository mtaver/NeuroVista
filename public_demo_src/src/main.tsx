import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Canvas } from '@react-three/fiber'
import { Bounds, GizmoHelper, GizmoViewport, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { decompress, isCompressed } from 'nifti-reader-js'
import { affinePoint, assertCompatible, readNiftiFile, validateMask, type Affine, type VolumeData } from './nifti'
import './styles.css'

type Label = { label: number; name: string; color: string; voxels: number; volume_ml: number }
type Metadata = { case: string; shape: [number, number, number]; spacing_mm: [number, number, number]; orientation: [string, string, string]; labels: Label[]; dice?: Record<string, number>; limitation?: string; model?: { name: string; version: string; licence: string } }
type MeshData = { label: number; vertices: number[][]; faces: number[][] }
type Plane = 'axial' | 'coronal' | 'sagittal'
type Dataset = { kind: 'sample' | 'user'; meta: Metadata; scan: Uint8Array; mask?: Uint16Array; meshes: MeshData[]; maskSource?: string }

const BASE = import.meta.env.BASE_URL
const SAMPLE_ASSET_VERSION = 'sample-v2'
const COLORS = ['#24dec7', '#ff6699', '#8777ff', '#ffb347', '#69a9ff', '#d6f06e', '#e782ff', '#68e59a']

async function ungzip(url: string) {
  const versionedUrl = `${url}?v=${SAMPLE_ASSET_VERSION}`
  const response = await fetch(versionedUrl, { cache: 'no-cache' })
  if (!response.ok) throw new Error(`Could not load ${url}`)
  const bytes = await response.arrayBuffer()
  if (!isCompressed(bytes)) throw new Error(`Sample asset ${url.split('/').pop()} is not valid gzip data.`)
  return new Uint8Array(decompress(bytes))
}

function displayVoxels(volume: VolumeData) {
  const [sx, sy, sz] = volume.shape
  const sampleStep = Math.max(1, Math.floor(volume.values.length / 250_000))
  const sample: number[] = []
  for (let index = 0; index < volume.values.length; index += sampleStep) sample.push(volume.values[index])
  sample.sort((a, b) => a - b)
  const low = sample[Math.floor(sample.length * 0.01)]
  const high = sample[Math.floor(sample.length * 0.99)]
  const scale = 255 / Math.max(high - low, 1e-6)
  const display = new Uint8Array(volume.values.length)
  for (let z = 0; z < sz; z++) for (let y = 0; y < sy; y++) for (let x = 0; x < sx; x++) {
    const source = x + y * sx + z * sx * sy
    display[x * sy * sz + y * sz + z] = Math.max(0, Math.min(255, Math.round((volume.values[source] - low) * scale)))
  }
  return display
}

function maskVoxels(volume: VolumeData) {
  const [sx, sy, sz] = volume.shape
  const result = new Uint16Array(volume.values.length)
  for (let z = 0; z < sz; z++) for (let y = 0; y < sy; y++) for (let x = 0; x < sx; x++) result[x * sy * sz + y * sz + z] = Math.round(volume.values[x + y * sx + z * sx * sy])
  return result
}

function makeMeshes(mask: Uint16Array, shape: [number, number, number], affine: Affine, labels: number[]) {
  const [sx, sy, sz] = shape
  const index = (x: number, y: number, z: number) => x * sy * sz + y * sz + z
  const directions = [
    { d: [-1, 0, 0], c: [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]] },
    { d: [1, 0, 0], c: [[1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 1]] },
    { d: [0, -1, 0], c: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]] },
    { d: [0, 1, 0], c: [[0, 1, 0], [0, 1, 1], [1, 1, 1], [1, 1, 0]] },
    { d: [0, 0, -1], c: [[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0]] },
    { d: [0, 0, 1], c: [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]] },
  ]
  return labels.map(label => {
    const vertices: number[][] = [], faces: number[][] = []
    for (let x = 0; x < sx; x++) for (let y = 0; y < sy; y++) for (let z = 0; z < sz; z++) {
      if (mask[index(x, y, z)] !== label) continue
      for (const side of directions) {
        const nx = x + side.d[0], ny = y + side.d[1], nz = z + side.d[2]
        if (nx >= 0 && nx < sx && ny >= 0 && ny < sy && nz >= 0 && nz < sz && mask[index(nx, ny, nz)] === label) continue
        if (faces.length >= 180_000) throw new Error(`Label ${label} surface is too complex for the browser limit (180,000 triangles).`)
        const base = vertices.length
        for (const corner of side.c) vertices.push(affinePoint(affine, x + corner[0] - 0.5, y + corner[1] - 0.5, z + corner[2] - 0.5))
        faces.push([base, base + 1, base + 2], [base, base + 2, base + 3])
      }
    }
    return { label, vertices, faces }
  })
}

function SliceCanvas({ plane, index, position, meta, scan, mask, opacity, visible, onMove }: { plane: Plane; index: number; position: [number, number, number]; meta: Metadata; scan: Uint8Array; mask?: Uint16Array; opacity: number; visible: Set<number>; onMove: (a: number, b: number) => void }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const [sx, sy, sz] = meta.shape
  const dimensions = plane === 'axial' ? [sx, sy] : plane === 'coronal' ? [sx, sz] : [sy, sz]
  useLayoutEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const [width, height] = dimensions
    canvas.width = width; canvas.height = height
    const context = canvas.getContext('2d')!, image = context.createImageData(width, height)
    for (let py = 0; py < height; py++) for (let px = 0; px < width; px++) {
      let x: number, y: number, z: number
      if (plane === 'axial') { x = px; y = height - 1 - py; z = index } else if (plane === 'coronal') { x = px; y = index; z = height - 1 - py } else { x = index; y = px; z = height - 1 - py }
      const source = x * sy * sz + y * sz + z, target = (py * width + px) * 4, gray = scan[source]
      image.data[target] = gray; image.data[target + 1] = gray; image.data[target + 2] = gray; image.data[target + 3] = 255
      const label = mask?.[source] ?? 0, config = meta.labels.find(value => value.label === label)
      if (config && visible.has(label)) {
        const color = new THREE.Color(config.color)
        image.data[target] = gray * (1 - opacity) + color.r * 255 * opacity
        image.data[target + 1] = gray * (1 - opacity) + color.g * 255 * opacity
        image.data[target + 2] = gray * (1 - opacity) + color.b * 255 * opacity
      }
    }
    context.putImageData(image, 0, 0)
    const cross = plane === 'axial' ? [position[0] / sx, 1 - position[1] / sy] : plane === 'coronal' ? [position[0] / sx, 1 - position[2] / sz] : [position[1] / sy, 1 - position[2] / sz]
    context.strokeStyle = '#68fff0'; context.lineWidth = 0.7; context.beginPath(); context.moveTo(cross[0] * width, 0); context.lineTo(cross[0] * width, height); context.moveTo(0, cross[1] * height); context.lineTo(width, cross[1] * height); context.stroke()
  }, [plane, index, position, meta, scan, mask, opacity, visible, dimensions[0], dimensions[1]])
  const horizontalSpacing = meta.spacing_mm[plane === 'sagittal' ? 1 : 0], verticalSpacing = meta.spacing_mm[plane === 'axial' ? 1 : 2]
  return <canvas ref={ref} style={{ aspectRatio: `${dimensions[0] * horizontalSpacing}/${dimensions[1] * verticalSpacing}` }} onClick={event => { const bounds = event.currentTarget.getBoundingClientRect(); onMove((event.clientX - bounds.left) / bounds.width, (event.clientY - bounds.top) / bounds.height) }} />
}

function Surface({ mesh, label, visible, opacity }: { mesh: MeshData; label: Label; visible: boolean; opacity: number }) {
  const geometry = useMemo(() => { const value = new THREE.BufferGeometry(); value.setAttribute('position', new THREE.Float32BufferAttribute(mesh.vertices.flat(), 3)); value.setIndex(mesh.faces.flat()); value.computeVertexNormals(); return value }, [mesh])
  return visible ? <mesh geometry={geometry}><meshStandardMaterial color={label.color} transparent opacity={opacity} side={THREE.DoubleSide} roughness={0.55} /></mesh> : null
}

function Demo() {
  const [dataset, setDataset] = useState<Dataset | null>(null), [scanVolume, setScanVolume] = useState<VolumeData | null>(null)
  const [loading, setLoading] = useState('Loading verified sample…'), [error, setError] = useState(''), [message, setMessage] = useState(''), [maskSource, setMaskSource] = useState('')
  const [position, setPosition] = useState<[number, number, number]>([0, 0, 0]), [opacity, setOpacity] = useState(0.52), [visible, setVisible] = useState(new Set<number>()), [surfaceOpacity, setSurfaceOpacity] = useState<Record<number, number>>({})
  const scanInput = useRef<HTMLInputElement>(null), maskInput = useRef<HTMLInputElement>(null)

  const applyDataset = (next: Dataset) => { setDataset(next); setPosition(next.meta.shape.map(value => Math.floor(value / 2)) as [number, number, number]); setVisible(new Set(next.meta.labels.map(label => label.label))); setSurfaceOpacity(Object.fromEntries(next.meta.labels.map((label, index) => [label.label, index === 1 ? 0.3 : 0.85]))); setError(''); setLoading('') }
  const loadSample = async () => {
    setLoading('Loading verified sample…'); setError(''); setMessage(''); setScanVolume(null); setMaskSource('')
    if (scanInput.current) scanInput.current.value = ''
    if (maskInput.current) maskInput.current.value = ''
    try {
      const [meta, scan, prediction, meshes] = await Promise.all([fetch(`${BASE}assets/demo-metadata.json?v=${SAMPLE_ASSET_VERSION}`, { cache: 'no-cache' }).then(response => { if (!response.ok) throw new Error('Sample metadata is unavailable.'); return response.json() }), ungzip(`${BASE}assets/scan-display-u8.bin.gz`), ungzip(`${BASE}assets/prediction-labels-u8.bin.gz`), ungzip(`${BASE}assets/prediction-meshes.json.gz`).then(value => JSON.parse(new TextDecoder().decode(value)))])
      const expectedVoxels = meta.shape.reduce((total: number, value: number) => total * value, 1)
      if (scan.length !== expectedVoxels || prediction.length !== expectedVoxels) throw new Error('Published sample voxel assets do not match the documented dimensions. Please reload the page.')
      applyDataset({ kind: 'sample', meta, scan, mask: new Uint16Array(prediction), meshes, maskSource: 'Precomputed AI prediction' })
    } catch (reason) { setLoading(''); setError(reason instanceof Error ? reason.message : String(reason)) }
  }
  useEffect(() => { void loadSample() }, [])

  const loadScan = async (file?: File) => {
    if (!file) return
    setLoading(`Reading ${file.name} locally…`); setError(''); setMessage(''); setScanVolume(null); setMaskSource(''); if (maskInput.current) maskInput.current.value = ''
    try {
      const volume = await readNiftiFile(file); setScanVolume(volume)
      applyDataset({ kind: 'user', scan: displayVoxels(volume), meshes: [], meta: { case: volume.name, shape: volume.shape, spacing_mm: volume.spacingMm, orientation: volume.orientation, labels: [] } })
      setMessage(`Loaded ${file.name} entirely in this browser. Select an accurate mask source before choosing a matching mask.`)
    } catch (reason) { setLoading(''); setError(reason instanceof Error ? reason.message : String(reason)); setDataset(null) }
  }
  const loadMask = async (file?: File) => {
    if (!file) return
    if (!scanVolume) { setError('Load a scan before loading its mask.'); return }
    if (!maskSource) { setError('Choose the mask source before selecting a mask.'); if (maskInput.current) maskInput.current.value = ''; return }
    setLoading(`Validating ${file.name} locally…`); setError(''); setMessage('')
    try {
      const volume = await readNiftiFile(file); assertCompatible(scanVolume, volume); const labels = validateMask(volume), mask = maskVoxels(volume), counts = new Map(labels.map(label => [label, 0]))
      mask.forEach(value => { if (value) counts.set(value, (counts.get(value) ?? 0) + 1) })
      const configs = labels.map((label, index) => ({ label, name: `Label ${label}`, color: COLORS[index % COLORS.length], voxels: counts.get(label) ?? 0, volume_ml: (counts.get(label) ?? 0) * scanVolume.voxelVolumeMl }))
      applyDataset({ kind: 'user', scan: displayVoxels(scanVolume), mask, meshes: makeMeshes(mask, scanVolume.shape, scanVolume.affine, labels), maskSource, meta: { case: scanVolume.name, shape: scanVolume.shape, spacing_mm: scanVolume.spacingMm, orientation: scanVolume.orientation, labels: configs } })
      setMessage(`Compatible mask loaded as “${maskSource}”. Volumes and surfaces were calculated locally.`)
    } catch (reason) { setLoading(''); setError(reason instanceof Error ? reason.message : String(reason)); if (maskInput.current) maskInput.current.value = '' }
  }
  const clearSession = () => { setDataset(null); setScanVolume(null); setMaskSource(''); setError(''); setMessage(''); setLoading(''); if (scanInput.current) scanInput.current.value = ''; if (maskInput.current) maskInput.current.value = '' }
  const meta = dataset?.meta, planes: Plane[] = ['axial', 'coronal', 'sagittal'], axis = { sagittal: 0, coronal: 1, axial: 2 } as const
  const move = (plane: Plane, a: number, b: number) => meta && setPosition(([x, y, z]) => plane === 'axial' ? [Math.round(a * (meta.shape[0] - 1)), Math.round((1 - b) * (meta.shape[1] - 1)), z] : plane === 'coronal' ? [Math.round(a * (meta.shape[0] - 1)), y, Math.round((1 - b) * (meta.shape[2] - 1))] : [x, Math.round(a * (meta.shape[1] - 1)), Math.round((1 - b) * (meta.shape[2] - 1))])

  return <><header><div className="brand">NeuroVista <span>PUBLIC DEMO</span></div><div className="offline">Browser-only · Files stay on this device</div></header><div className="notice">Research and education only — not for clinical diagnosis.</div><main>
    <section className="hero"><div><div className="eyebrow">LOCAL BROWSER WORKSPACE</div><h1>Explore NIfTI scans without a server.</h1></div><div className="status">NO AUTOMATIC AI ANALYSIS</div></section>
    <section className="upload-panel panel" aria-label="Local NIfTI files"><div><h2>1 · Scan</h2><p>.nii or .nii.gz · maximum 256 MiB</p><label className="file-button">Choose scan<input ref={scanInput} type="file" accept=".nii,.nii.gz" onChange={event => void loadScan(event.target.files?.[0])} /></label></div><div><h2>2 · Matching mask</h2><p>Same 3D dimensions, spatial units and affine</p><select aria-label="Mask source" value={maskSource} onChange={event => setMaskSource(event.target.value)} disabled={!scanVolume}><option value="">Choose mask source…</option><option>Expert reference mask</option><option>User annotation</option><option>Synthetic annotation</option><option>AI prediction generated elsewhere</option><option>Other research annotation</option></select><label className={`file-button ${!scanVolume || !maskSource ? 'disabled' : ''}`}>Choose mask<input ref={maskInput} type="file" accept=".nii,.nii.gz" disabled={!scanVolume || !maskSource} onChange={event => void loadMask(event.target.files?.[0])} /></label></div><div className="session-actions"><button onClick={() => void loadSample()}>Open verified sample</button><button onClick={clearSession}>Clear session</button></div></section>
    <p className="privacy">Files are decoded in volatile browser memory. NeuroVista does not transmit, upload, or retain them. Closing or clearing this page discards the session.</p>
    {loading && <div className="feedback busy">{loading}</div>}{error && <div className="feedback error" role="alert">{error}</div>}{message && <div className="feedback success" role="status">{message}</div>}
    {!dataset && !loading && <section className="empty"><h2>No scan loaded</h2><p>Choose a local 3D NIfTI scan or reopen the verified sample.</p></section>}
    {dataset && meta && <><section className="dataset-head"><div><div className="eyebrow">{dataset.kind === 'sample' ? 'VERIFIED WORKFLOW DEMONSTRATION' : 'LOCAL USER FILE'}</div><h2>{meta.case}</h2></div>{dataset.maskSource && <div className="source"><span>Active mask source</span><b>{dataset.maskSource}</b></div>}</section>
      <section className="workspace"><aside><h2>Display controls</h2><label>Overlay opacity <output>{Math.round(opacity * 100)}%</output><input type="range" min="0" max="1" step=".05" value={opacity} onChange={event => setOpacity(+event.target.value)} /></label>{meta.labels.length > 0 ? <div className="legend">{meta.labels.map(label => <div key={label.label}><label><input type="checkbox" checked={visible.has(label.label)} onChange={() => setVisible(current => { const next = new Set(current); next.has(label.label) ? next.delete(label.label) : next.add(label.label); return next })} /><i style={{ background: label.color }} /><span>{label.name}</span></label><b>{label.volume_ml.toFixed(3)} mL</b></div>)}</div> : <p className="no-mask">No mask loaded. Slice viewing is available without an annotation.</p>}<dl><div><dt>Dimensions</dt><dd>{meta.shape.join(' × ')}</dd></div><div><dt>Spacing</dt><dd>{meta.spacing_mm.map(value => value.toFixed(3)).join(' × ')} mm</dd></div><div><dt>Orientation</dt><dd>{meta.orientation.join(' · ')}</dd></div>{dataset.kind === 'sample' && meta.model && <div><dt>Model</dt><dd>MONAI {meta.model.version}</dd></div>}</dl></aside>
        <div className="views">{planes.map(plane => <article className="slice" key={`${dataset.kind}-${meta.case}-${plane}`}><header><b>{plane}</b><span>Slice {position[axis[plane]] + 1} / {meta.shape[axis[plane]]}</span></header><SliceCanvas plane={plane} index={position[axis[plane]]} position={position} meta={meta} scan={dataset.scan} mask={dataset.mask} opacity={opacity} visible={visible} onMove={(a, b) => move(plane, a, b)} /><input aria-label={`${plane} slice`} type="range" min="0" max={meta.shape[axis[plane]] - 1} value={position[axis[plane]]} onChange={event => setPosition(value => value.map((entry, index) => index === axis[plane] ? +event.target.value : entry) as [number, number, number])} /></article>)}</div></section>
      {dataset.meshes.length > 0 && <section className="panel three"><div className="section-head"><div><div className="eyebrow">LOCAL LABEL GEOMETRY</div><h2>Interactive 3D surfaces</h2></div><span>Drag to rotate · Scroll to zoom</span></div><div className="three-layout"><div className="canvas"><Canvas camera={{ position: [260, 260, 260], fov: 42 }}><ambientLight intensity={1.3} /><directionalLight position={[2, 4, 3]} intensity={2} /><Bounds fit clip observe margin={1.15}>{dataset.meshes.map(mesh => <Surface key={mesh.label} mesh={mesh} label={meta.labels.find(value => value.label === mesh.label)!} visible={visible.has(mesh.label)} opacity={surfaceOpacity[mesh.label] ?? 0.8} />)}</Bounds><OrbitControls makeDefault /><GizmoHelper alignment="bottom-right" margin={[70, 70]}><GizmoViewport axisColors={['#ff667b', '#68e59a', '#65a9ff']} labelColor="white" /></GizmoHelper></Canvas></div><div className="surface-controls">{meta.labels.map(label => <label key={label.label}><span><i style={{ background: label.color }} />{label.name}</span><input type="range" min=".05" max="1" step=".05" value={surfaceOpacity[label.label] ?? 0.8} onChange={event => setSurfaceOpacity(value => ({ ...value, [label.label]: +event.target.value }))} /></label>)}<small>Rendering opacity does not alter voxel-derived physical volume measurements.</small></div></div></section>}
      {dataset.kind === 'sample' && meta.dice && <section className="panel comparison"><div className="section-head"><div><div className="eyebrow">SINGLE-CASE COMPARISON</div><h2>Prediction versus MSD expert reference</h2></div></div><div className="dice"><div><b>{meta.dice.whole_tumour.toFixed(6)}</b><span>Whole tumour Dice</span></div><div><b>{meta.dice.tumour_core.toFixed(6)}</b><span>Tumour core Dice</span></div><div><b>{meta.dice.enhancing_tumour.toFixed(6)}</b><span>Enhancing tumour Dice</span></div></div><details><summary>Limitations and validation status</summary><div className="limitations"><span className="status">NOT INDEPENDENT VALIDATION</span><p>{meta.limitation} This single case demonstrates a completed technical workflow, not diagnostic accuracy, clinical performance, or cohort validation.</p></div></details></section>}
      {dataset.kind === 'sample' && <section className="panel attribution"><h2>Data attribution and licence</h2><p>Transformed display data derives from Medical Segmentation Decathlon Task01 BrainTumour case BRATS_457, redistributed under <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. Source: <a href="https://medicaldecathlon.com/">Medical Segmentation Decathlon</a>. Citation: Antonelli et al., <a href="https://doi.org/10.1038/s41467-022-30695-9">Nature Communications 13, 4128 (2022)</a>. The AI result was generated previously with Project MONAI model bundle v0.5.4 and is not an expert label.</p></section>}</>}
  </main><footer>NeuroVista public workspace · Static GitHub Pages build · Browser-local NIfTI processing · No inference endpoint</footer></>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><Demo /></React.StrictMode>)
