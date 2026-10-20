import { Canvas, useThree } from '@react-three/fiber'
import { Environment, OrbitControls } from '@react-three/drei'
import { Expand, RotateCcw } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { getMesh } from '../api'
import type { MeshData } from '../types'

const COLORS = ['#24dec7', '#ff6699', '#ffbe4b', '#8777ff', '#59b8ff']
type ViewName = 'reset' | 'axial' | 'coronal' | 'sagittal'
type ViewRequest = { name: ViewName; token: number }

function Surface({ data, color, opacity }: { data: MeshData; color: string; opacity: number }) {
  const geometry = useMemo(() => {
    const result = new THREE.BufferGeometry()
    result.setAttribute('position', new THREE.Float32BufferAttribute(data.vertices.flat(), 3))
    result.setIndex(data.faces.flat())
    result.computeVertexNormals()
    return result
  }, [data])
  useEffect(() => () => geometry.dispose(), [geometry])
  return <mesh geometry={geometry}><meshStandardMaterial color={color} roughness={0.55} metalness={0.05} transparent opacity={opacity} depthWrite={opacity >= .95} side={THREE.DoubleSide} /></mesh>
}

function CameraRig({ box, request }: { box: THREE.Box3; request: ViewRequest }) {
  const { camera, size } = useThree()
  const controls = useRef<any>(null)
  useLayoutEffect(() => {
    if (box.isEmpty()) return
    const centre = box.getCenter(new THREE.Vector3())
    const dimensions = box.getSize(new THREE.Vector3())
    const perspective = camera as THREE.PerspectiveCamera
    const fov = THREE.MathUtils.degToRad(perspective.fov)
    const aspect = Math.max(size.width / Math.max(size.height, 1), .1)
    const distance = Math.max(dimensions.y, dimensions.x / aspect, dimensions.z) / (2 * Math.tan(fov / 2)) * 1.35
    const direction = request.name === 'axial' ? new THREE.Vector3(0, 0, 1)
      : request.name === 'coronal' ? new THREE.Vector3(0, -1, 0)
      : request.name === 'sagittal' ? new THREE.Vector3(1, 0, 0)
      : new THREE.Vector3(1, -1, 1).normalize()
    perspective.up.set(0, 0, 1)
    if (request.name === 'axial') perspective.up.set(0, 1, 0)
    perspective.position.copy(centre).add(direction.multiplyScalar(distance))
    perspective.near = Math.max(distance / 100, .1)
    perspective.far = distance * 10
    perspective.updateProjectionMatrix()
    controls.current?.target.copy(centre)
    controls.current?.update()
  }, [box, camera, request, size.width, size.height])
  return <OrbitControls ref={controls} makeDefault />
}

export function MeshViewer({ sessionId, labels, labelNames }: { sessionId: string; labels: number[]; labelNames: Record<string, string> }) {
  const [meshes, setMeshes] = useState<Record<number, MeshData>>({})
  const [shown, setShown] = useState<number[]>(labels)
  const [opacity, setOpacity] = useState<Record<number, number>>({})
  const [view, setView] = useState<ViewRequest>({ name: 'reset', token: 0 })
  const [error, setError] = useState('')
  const [fullscreen, setFullscreen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setShown(labels)
    setOpacity(Object.fromEntries(labels.map(label => [label, label === 2 && labels.includes(4) ? .28 : .82])))
    let cancelled = false
    setMeshes({}); setError('')
    Promise.all(labels.map(async label => [label, await getMesh(sessionId, label)] as const))
      .then(entries => { if (!cancelled) { setMeshes(Object.fromEntries(entries)); setView(v => ({ name: 'reset', token: v.token + 1 })) } })
      .catch(err => setError(err.message))
    return () => { cancelled = true }
  }, [sessionId, labels.join(',')])
  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === wrap.current)
    document.addEventListener('fullscreenchange', update)
    return () => document.removeEventListener('fullscreenchange', update)
  }, [])

  const box = useMemo(() => {
    const result = new THREE.Box3()
    Object.values(meshes).forEach(mesh => mesh.vertices.forEach(vertex => result.expandByPoint(new THREE.Vector3(...vertex))))
    return result
  }, [meshes])
  const chooseView = (name: ViewName) => setView(v => ({ name, token: v.token + 1 }))
  const toggleFullscreen = async () => {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await wrap.current?.requestFullscreen()
  }

  if (error) return <div className="three-state error-state">{error}</div>
  if (!labels.length) return <div className="three-state">Upload a compatible mask to build 3D surfaces.</div>
  if (Object.keys(meshes).length < labels.length) return <div className="three-state"><span className="spinner" />Building surfaces locally…</div>
  return <div className={`three-workspace ${fullscreen ? 'is-fullscreen' : ''}`} ref={wrap}>
    <div className="three-toolbar" aria-label="3D camera controls">
      <button onClick={() => chooseView('reset')}><RotateCcw size={14}/>Reset camera</button>
      <button onClick={() => chooseView('axial')}>Axial</button><button onClick={() => chooseView('coronal')}>Coronal</button><button onClick={() => chooseView('sagittal')}>Sagittal</button>
      <button onClick={toggleFullscreen}><Expand size={14}/>{fullscreen ? 'Exit fullscreen' : 'Fullscreen'}</button>
    </div>
    <div className="three-layout">
      <div className="canvas-wrap" aria-label="Interactive 3D segmentation surfaces">
        <Canvas camera={{ position: [0, 0, 220], fov: 42 }}><ambientLight intensity={1.2} /><directionalLight position={[10, 12, 8]} intensity={2} />
          {shown.map(label => meshes[label] && <Surface key={label} data={meshes[label]} color={COLORS[(label - 1) % COLORS.length]} opacity={opacity[label] ?? .8} />)}
          <CameraRig box={box} request={view} /><Environment preset="city" />
        </Canvas>
      </div>
      <aside className="three-regions"><b>3D regions</b>{labels.map(label => <div key={label}>
        <label><input type="checkbox" checked={shown.includes(label)} onChange={() => setShown(current => current.includes(label) ? current.filter(value => value !== label) : [...current, label])}/><i style={{background: COLORS[(label - 1) % COLORS.length]}}/><span>{labelNames[String(label)] ?? `Region ${label}`}</span></label>
        <label className="opacity-control"><span>Opacity</span><input aria-label={`3D opacity for ${labelNames[String(label)] ?? `Region ${label}`}`} type="range" min="0.05" max="1" step="0.05" value={opacity[label] ?? .8} onChange={event => setOpacity(current => ({...current, [label]: Number(event.target.value)}))}/><output>{Math.round((opacity[label] ?? .8) * 100)}%</output></label>
      </div>)}</aside>
    </div>
    <small className="geometry-note">Visual transparency and smooth shading affect rendering only; measurements remain derived from the unchanged voxel mask and affine.</small>
  </div>
}
