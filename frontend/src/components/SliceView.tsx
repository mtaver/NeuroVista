import { Maximize2 } from 'lucide-react'
import type { Labels, Plane } from '../types'

type Props = { plane: Plane; title: string; url: string; index: number; max: number; labels: Labels; aspect: number; crosshair: [number, number]; onSlice: (value: number) => void; onCrosshair: (x: number, y: number) => void }

export function SliceView({ plane, title, url, index, max, labels, aspect, crosshair, onSlice, onCrosshair }: Props) {
  return <section className="slice-card" aria-label={`${title} MRI view`}>
    <header><span>{title}</span><small>{index + 1} / {max}</small></header>
    <div className="slice-frame" style={{ aspectRatio: String(aspect) }} onClick={event => {
      const rect = event.currentTarget.getBoundingClientRect()
      onCrosshair((event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height)
    }}>
      <img src={url} alt={`${title} MRI slice`} draggable={false} />
      <span className="orientation top">{labels.top}</span><span className="orientation bottom">{labels.bottom}</span>
      <span className="orientation left">{labels.left}</span><span className="orientation right">{labels.right}</span>
      <i className="crosshair x" style={{ top: `${crosshair[1] * 100}%` }} /><i className="crosshair y" style={{ left: `${crosshair[0] * 100}%` }} />
      <Maximize2 className="expand" size={15} />
    </div>
    <label className="slider-row"><span>Slice</span><input aria-label={`${title} slice`} type="range" min="0" max={max - 1} value={index} onChange={e => onSlice(Number(e.target.value))} /></label>
  </section>
}

