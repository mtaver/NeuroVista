import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Activity, BadgeCheck, BrainCircuit, CircleHelp, Database, Download, Eraser, FileUp, Layers3, MapPin, RotateCcw, ScanLine, ShieldCheck, Sparkles } from 'lucide-react'
import { clearSession, createSession, getForegroundCentre, loadSynthetic, loadVerifiedDemonstration, sliceUrl, uploadMask, uploadScan } from './api'
import { MeshViewer } from './components/MeshViewer'
import { SliceView } from './components/SliceView'
import type { Mask, Plane, Scan, VerifiedDemonstration } from './types'
import './styles.css'

const COLORS = ['#24dec7', '#ff6699', '#ffbe4b', '#8777ff', '#59b8ff']
const planeAxis: Record<Plane, number> = { sagittal: 0, coronal: 1, axial: 2 }

function UploadButton({ label, accept, onFile, disabled = false }: { label: string; accept: string; onFile: (file: File) => void; disabled?: boolean }) {
  return <label className={`button secondary ${disabled ? 'disabled' : ''}`}><FileUp size={16} />{label}<input hidden disabled={disabled} type="file" accept={accept} onChange={e => e.target.files?.[0] && onFile(e.target.files[0])} /></label>
}

export default function App() {
  const [sessionId, setSessionId] = useState('')
  const [scan, setScan] = useState<Scan | null>(null)
  const [mask, setMask] = useState<Mask | null>(null)
  const [position, setPosition] = useState<[number, number, number]>([0, 0, 0])
  const [windowLevel, setWindowLevel] = useState({ window: 1000, level: 500 })
  const [opacity, setOpacity] = useState(.5)
  const [visible, setVisible] = useState<number[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [maskKind, setMaskKind] = useState<'reference' | 'annotation' | 'prediction'>('reference')
  const [zoom, setZoom] = useState(1)
  const [demonstration, setDemonstration] = useState<VerifiedDemonstration | null>(null)
  const [jumpFeedback, setJumpFeedback] = useState<{ kind: 'success' | 'error'; message: string } | null>(null)
  const viewsRef = useRef<HTMLDivElement>(null)

  useEffect(() => { createSession().then(v => setSessionId(v.session_id)).catch(e => setError(e.message)) }, [])

  const setLoaded = (nextScan: Scan, nextMask: Mask | null, nextDemonstration: VerifiedDemonstration | null = null) => {
    setScan(nextScan); setMask(nextMask); setVisible(nextMask?.labels ?? [])
    setDemonstration(nextDemonstration)
    setJumpFeedback(null)
    setPosition(nextScan.metadata.shape.map(v => Math.floor(v / 2)) as [number, number, number])
    const [low, high] = nextScan.metadata.intensity; setWindowLevel({ window: Math.max(high - low, 1), level: (high + low) / 2 })
    setError(''); setZoom(1)
  }
  const run = async (message: string, work: () => Promise<void>) => { setBusy(message); setError(''); try { await work() } catch (e) { setError(e instanceof Error ? e.message : 'Unexpected error') } finally { setBusy('') } }
  const handleScan = (file: File) => run('Validating MRI geometry…', async () => setLoaded(await uploadScan(sessionId, file), null))
  const handleMask = (file: File) => run('Checking mask compatibility…', async () => { const result = await uploadMask(sessionId, file, maskKind); setMask(result); setVisible(result.labels); setJumpFeedback(null) })
  const synthetic = () => run('Creating synthetic demonstration…', async () => { const result = await loadSynthetic(sessionId); setLoaded(result.scan, result.mask) })
  const verifiedDemo = () => run('Verifying and opening BRATS_457…', async () => { const result = await loadVerifiedDemonstration(sessionId); setLoaded(result.scan, result.mask, result.demonstration) })
  const jumpUnavailableReason = !mask ? 'Load a prediction mask first.' : mask.kind !== 'prediction' ? 'Available only when the active mask is an imported AI prediction.' : !mask.labels.length ? 'The active prediction has no foreground labels.' : ''
  const jumpDisabledReason = jumpUnavailableReason || (busy ? 'Wait for the current local operation to finish.' : '')
  const jumpToPrediction = async () => {
    if (jumpUnavailableReason || busy) return
    setBusy('Locating predicted region…'); setError(''); setJumpFeedback(null)
    try {
      const result = await getForegroundCentre(sessionId)
      setPosition(result.voxel)
      setJumpFeedback({ kind: 'success', message: `Centred all views on predicted foreground voxel [${result.voxel.join(', ')}].` })
      requestAnimationFrame(() => viewsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : 'Unexpected local API error'
      const message = `Could not locate predicted foreground: ${detail} Reload the verified demonstration or import a compatible non-empty prediction mask.`
      setError(message); setJumpFeedback({ kind: 'error', message })
    } finally { setBusy('') }
  }
  const reset = () => scan && setLoaded(scan, mask, demonstration)
  const clear = () => run('Clearing temporary files…', async () => { await clearSession(sessionId); const next = await createSession(); setSessionId(next.session_id); setScan(null); setMask(null); setDemonstration(null); setJumpFeedback(null); setVisible([]) })

  const urls = useMemo(() => {
    if (!scan) return null
    const args = [sessionId, windowLevel.window, windowLevel.level, opacity, visible] as const
    return Object.fromEntries((['axial', 'coronal', 'sagittal'] as Plane[]).map(p => [p, sliceUrl(args[0], p, position[planeAxis[p]], args[1], args[2], args[3], args[4])])) as Record<Plane, string>
  }, [scan, sessionId, position, windowLevel, opacity, visible])

  const crosshair = (plane: Plane): [number, number] => {
    if (!scan) return [.5, .5]
    const [x, y, z] = position, [sx, sy, sz] = scan.metadata.shape
    return plane === 'axial' ? [x / (sx - 1), 1 - y / (sy - 1)] : plane === 'coronal' ? [x / (sx - 1), 1 - z / (sz - 1)] : [y / (sy - 1), 1 - z / (sz - 1)]
  }
  const moveCrosshair = (plane: Plane, nx: number, ny: number) => {
    if (!scan) return
    const [sx, sy, sz] = scan.metadata.shape
    setPosition(([x, y, z]) => plane === 'axial' ? [Math.round(nx*(sx-1)), Math.round((1-ny)*(sy-1)), z] : plane === 'coronal' ? [Math.round(nx*(sx-1)), y, Math.round((1-ny)*(sz-1))] : [x, Math.round(nx*(sy-1)), Math.round((1-ny)*(sz-1))])
  }
  const aspect = (plane: Plane) => {
    if (!scan) return 1
    const [sx, sy, sz] = scan.metadata.shape, [dx, dy, dz] = scan.metadata.spacing
    return plane === 'axial' ? (sx*dx)/(sy*dy) : plane === 'coronal' ? (sx*dx)/(sz*dz) : (sy*dy)/(sz*dz)
  }

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#workspace"><span><BrainCircuit size={22} /></span><b>NeuroVista</b><em>RESEARCH</em></a>
      <nav aria-label="Main navigation"><a href="#samples">Samples</a><a className="active" href="#workspace">MRI Workspace</a><a href="#segmentation">Segmentation</a><a href="#results">Results</a><a href="#documentation">Documentation</a></nav>
      <div className="local-status"><i /> Local processing</div>
    </header>
    <div className="notice"><ShieldCheck size={15} /> Research and education only — not for clinical diagnosis. Files stay on this computer and are removed when the session is cleared.</div>
    <main id="workspace">
      <section className="hero" id="samples"><div><span className="eyebrow">STAGE 1 · MRI WORKSPACE</span><h1>Explore anatomy.<br/><span>Keep the geometry honest.</span></h1><p>Inspect NIfTI volumes and verified segmentation masks across linked anatomical planes and 3D surfaces.</p></div>
        <div className="hero-actions"><button className="button primary" onClick={verifiedDemo} disabled={!sessionId}><BadgeCheck size={16}/>Open verified demonstration</button><UploadButton label="Upload MRI" accept=".nii,.nii.gz" onFile={handleScan} /><button className="button ghost" onClick={synthetic} disabled={!sessionId}><Sparkles size={16}/>Try synthetic sample</button></div>
      </section>

      {error && <div role="alert" className="alert error-state"><CircleHelp size={18}/><div><b>Could not complete that action</b><span>{error}</span></div></div>}
      {busy && <div className="alert loading"><span className="spinner"/><div><b>{busy}</b><span>Processing locally; no scan data is sent elsewhere.</span></div></div>}

      {!scan ? <section className="empty-state"><div className="scan-glyph"><ScanLine size={62}/><i/></div><h2>Your workspace is ready</h2><p>Open the preserved BRATS_457 technical demonstration in one click, upload a 3D NIfTI volume, or use synthetic data.</p><div><button className="button primary" onClick={verifiedDemo} disabled={!sessionId}><BadgeCheck size={16}/>Open verified demonstration</button><UploadButton label="Choose NIfTI scan" accept=".nii,.nii.gz" onFile={handleScan}/><button className="button ghost" onClick={synthetic}><Sparkles size={16}/>Synthetic demonstration</button></div><small>The verified demonstration is available only when all five ignored local artifacts pass hash and geometry checks.</small></section> : <>
        {scan.synthetic && <div className="synthetic-badge"><Sparkles size={15}/> Synthetic demonstration — not a patient scan</div>}
        {demonstration && <div className="synthetic-badge verified"><BadgeCheck size={15}/> Verified workflow demonstration · BRATS_457 · AI prediction imported</div>}
        <section className="workspace-grid">
          <aside className="panel controls">
            <div className="panel-heading"><div><span>01</span><h2>Scan</h2></div><Activity size={18}/></div>
            <div className="file-card"><ScanLine size={22}/><div><b>{scan.name}</b><span>{scan.metadata.shape.join(' × ')} voxels</span></div><span className="valid">VALID</span></div>
            <dl><div><dt>Voxel spacing</dt><dd>{scan.metadata.spacing.map(v => v.toFixed(2)).join(' × ')} {scan.metadata.units}</dd></div><div><dt>Orientation</dt><dd>{scan.metadata.orientation.join(' · ')}</dd></div><div><dt>Data type</dt><dd>{scan.metadata.dtype}</dd></div></dl>
            <div className="section-label">Display</div>
            <label>Window <output>{windowLevel.window.toFixed(0)}</output><input type="range" min="1" max={Math.max(3000, windowLevel.window*2)} value={windowLevel.window} onChange={e => setWindowLevel(v => ({...v, window: Number(e.target.value)}))}/></label>
            <label>Level <output>{windowLevel.level.toFixed(0)}</output><input type="range" min={scan.metadata.intensity[0]} max={scan.metadata.intensity[1]} value={windowLevel.level} onChange={e => setWindowLevel(v => ({...v, level: Number(e.target.value)}))}/></label>
            <label>Zoom <output>{zoom.toFixed(1)}×</output><input type="range" min="1" max="2" step="0.1" value={zoom} onChange={e => setZoom(Number(e.target.value))}/></label>
            <button className="text-button" onClick={reset}><RotateCcw size={14}/>Reset view</button>
            <div className="panel-heading compact"><div><span>02</span><h2>Mask</h2></div><Layers3 size={18}/></div>
            {mask && <><div className="active-mask"><span>Active mask provenance</span><div className={`provenance ${mask.kind}`}>{mask.kind === 'reference' ? 'UPLOADED REFERENCE MASK' : mask.kind === 'annotation' ? 'USER ANNOTATION' : 'AI PREDICTION · IMPORTED'}</div><b>{mask.name}</b></div>{mask.kind === 'prediction' && <p className="prediction-note">Generated outside this local viewer. This is not an expert reference mask or a live model connection.</p>}<button type="button" className="button jump-button" onClick={jumpToPrediction} disabled={Boolean(jumpDisabledReason)} aria-describedby={jumpDisabledReason ? 'jump-availability' : undefined}><MapPin size={15}/>Jump to predicted region</button>{jumpDisabledReason && <p id="jump-availability" className="control-explanation">{jumpDisabledReason}</p>}<label>2D overlay opacity <output>{Math.round(opacity*100)}%</output><input type="range" min="0" max="1" step="0.05" value={opacity} onChange={e => setOpacity(Number(e.target.value))}/></label><div className="legend">{mask.measurements.map(m => <label key={m.label}><input type="checkbox" checked={visible.includes(m.label)} onChange={() => setVisible(v => v.includes(m.label) ? v.filter(x => x !== m.label) : [...v, m.label])}/><i style={{background: COLORS[(m.label - 1)%COLORS.length]}}/><span>{mask.label_names[String(m.label)] ?? `Region ${m.label}`}<small>{m.volume_ml.toFixed(2)} mL</small></span></label>)}</div></>}
            <div className="upload-source"><span>Source for next mask upload</span><select value={maskKind} onChange={e => setMaskKind(e.target.value as 'reference'|'annotation'|'prediction')} aria-label="Source for next mask upload"><option value="reference">Expert reference mask</option><option value="annotation">User annotation</option><option value="prediction">Imported AI prediction</option></select><UploadButton label={mask ? 'Replace active mask' : 'Upload corresponding mask'} accept=".nii,.nii.gz" onFile={handleMask}/></div>
          </aside>
          <div className="viewer-column" ref={viewsRef} style={{'--zoom': zoom, scrollMarginTop: 116} as CSSProperties}>
            {jumpFeedback && <div className={`jump-feedback ${jumpFeedback.kind}`} role={jumpFeedback.kind === 'error' ? 'alert' : 'status'} aria-live="polite"><MapPin size={16}/><span>{jumpFeedback.message}</span></div>}
            <div className="slice-grid">{(['axial','coronal','sagittal'] as Plane[]).map(plane => <SliceView key={plane} plane={plane} title={plane[0].toUpperCase()+plane.slice(1)} url={urls![plane]} index={position[planeAxis[plane]]} max={scan.metadata.shape[planeAxis[plane]]} labels={scan.orientation_labels[plane]} aspect={aspect(plane)} crosshair={crosshair(plane)} onCrosshair={(x,y) => moveCrosshair(plane,x,y)} onSlice={value => setPosition(v => v.map((n,i) => i === planeAxis[plane] ? value : n) as [number,number,number])}/>)}</div>
            <section className="panel three-panel"><header><div><span className="eyebrow">VERIFIED MASK GEOMETRY</span><h2>Interactive 3D surfaces</h2></div><small>Drag to rotate · Scroll to zoom</small></header><MeshViewer sessionId={sessionId} labels={mask?.labels ?? []} labelNames={mask?.label_names ?? {}}/></section>
          </div>
        </section>
        {demonstration && <section className="panel demo-comparison"><header><div><span className="eyebrow">SINGLE-CASE TECHNICAL DEMONSTRATION</span><h2>Prediction compared with the MSD expert reference</h2></div><span className="status-pill">NOT INDEPENDENT VALIDATION</span></header><div className="dice-grid"><div><b>{demonstration.dice.whole_tumour.toFixed(6)}</b><span>Whole tumour Dice</span></div><div><b>{demonstration.dice.tumour_core.toFixed(6)}</b><span>Tumour core Dice</span></div><div><b>{demonstration.dice.enhancing_tumour.toFixed(6)}</b><span>Enhancing tumour Dice</span></div></div><p><CircleHelp size={16}/><span>{demonstration.limitation} These values demonstrate one completed file workflow; they do not establish diagnostic accuracy or cohort performance.</span></p></section>}
        <section id="results" className="results-row"><div><Database size={20}/><span><b>Research results</b><small>Measurements use affine voxel volume and verified {scan.metadata.units} spatial units.</small></span></div><div><a className="button secondary" href={`/api/sessions/${sessionId}/export`} download><Download size={16}/>Export JSON</a><button className="button danger" onClick={clear}><Eraser size={16}/>Clear session</button></div></section>
      </>}

      <section id="segmentation" className="roadmap"><span className="eyebrow">INFERENCE STATUS</span><div><h2>Local inference not connected</h2><p>{mask?.kind === 'prediction' ? 'Cloud-generated AI prediction imported. This is a file import, not a live Colab connection.' : 'NeuroVista does not run a model locally. A compatible prediction can be imported as a file; no prediction is simulated.'}</p></div><span className="status-pill">{mask?.kind === 'prediction' ? 'CLOUD OUTPUT · IMPORTED' : 'LOCAL MODEL · OFF'}</span></section>
    </main>
    <footer id="documentation"><span>NeuroVista 0.1 · Local research workspace</span><span>Uploads: temporary local storage · Setup details are in README.md</span></footer>
  </div>
}

