import { Canvas } from '@react-three/fiber'
import { Bounds, Environment, OrbitControls } from '@react-three/drei'
import { useEffect, useMemo, useState } from 'react'
import * as THREE from 'three'
import { getMesh } from '../api'
import type { MeshData } from '../types'

const COLORS = ['#24dec7', '#ff6699', '#ffbe4b', '#8777ff', '#59b8ff']

function Surface({ data, color }: { data: MeshData; color: string }) {
  const geometry = useMemo(() => {
    const result = new THREE.BufferGeometry()
    result.setAttribute('position', new THREE.Float32BufferAttribute(data.vertices.flat(), 3))
    result.setIndex(data.faces.flat())
    result.computeVertexNormals()
    result.center()
    return result
  }, [data])
  useEffect(() => () => geometry.dispose(), [geometry])
  return <mesh geometry={geometry}><meshStandardMaterial color={color} roughness={0.55} metalness={0.05} transparent opacity={0.9} side={THREE.DoubleSide} /></mesh>
}

export function MeshViewer({ sessionId, labels, visible }: { sessionId: string; labels: number[]; visible: number[] }) {
  const [meshes, setMeshes] = useState<Record<number, MeshData>>({})
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    Promise.all(labels.map(async label => [label, await getMesh(sessionId, label)] as const))
      .then(entries => { if (!cancelled) setMeshes(Object.fromEntries(entries)) })
      .catch(err => setError(err.message))
    return () => { cancelled = true }
  }, [sessionId, labels.join(',')])
  if (error) return <div className="three-state error-state">{error}</div>
  if (!labels.length) return <div className="three-state">Upload a compatible mask to build 3D surfaces.</div>
  if (Object.keys(meshes).length < labels.length) return <div className="three-state"><span className="spinner" />Building surfaces locally…</div>
  return <div className="canvas-wrap" aria-label="Interactive 3D segmentation surfaces">
    <Canvas camera={{ position: [0, 0, 220], fov: 42 }}><ambientLight intensity={1.2} /><directionalLight position={[10, 12, 8]} intensity={2} />
      <Bounds fit clip observe margin={1.25}>{visible.map(label => meshes[label] && <Surface key={label} data={meshes[label]} color={COLORS[(label - 1) % COLORS.length]} />)}</Bounds>
      <OrbitControls makeDefault /><Environment preset="city" /></Canvas>
  </div>
}

