'use client'

import { useState } from 'react'
import { X, ZoomIn, ZoomOut, ExternalLink } from 'lucide-react'

interface PdfModalProps {
  url: string
  onClose: () => void
}

export function PdfModal({ url, onClose }: PdfModalProps) {
  // zoom is applied as a URL fragment hint for the browser PDF viewer
  const [zoom, setZoom] = useState(100)

  const zoomIn  = () => setZoom(z => Math.min(200, z + 25))
  const zoomOut = () => setZoom(z => Math.max(50,  z - 25))

  // The #zoom= fragment is supported by Chrome/Edge's built-in PDF viewer
  const iframeSrc = `${url}#toolbar=1&navpanes=0&zoom=${zoom}`

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="relative flex flex-col"
        style={{
          position: 'absolute',
          inset: '12px',
          background: 'rgba(2,6,23,0.98)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 16,
          overflow: 'hidden',
        }}
      >
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/10 shrink-0">
          <div className="flex items-center gap-2">
            <button
              onClick={zoomOut}
              disabled={zoom <= 50}
              className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-muted-foreground hover:text-foreground disabled:opacity-30"
              title="Zoom out"
            >
              <ZoomOut size={14} />
            </button>
            <span className="text-xs font-mono text-muted-foreground w-12 text-center select-none">
              {zoom}%
            </span>
            <button
              onClick={zoomIn}
              disabled={zoom >= 200}
              className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-muted-foreground hover:text-foreground disabled:opacity-30"
              title="Zoom in"
            >
              <ZoomIn size={14} />
            </button>
            <span className="text-xs text-muted-foreground/40 mx-1">|</span>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ExternalLink size={12} /> Open in new tab
            </a>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-muted-foreground hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        {/* PDF iframe — browser renders with native viewer (Chrome/Edge) */}
        <iframe
          key={zoom} // remount on zoom change so the fragment updates
          src={iframeSrc}
          className="flex-1 w-full border-0"
          title="Resume PDF"
        />
      </div>
    </div>
  )
}
