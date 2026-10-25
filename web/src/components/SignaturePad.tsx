import { useEffect, useRef, type MouseEvent, type TouchEvent } from 'react'

type Props = {
  value?: string | null
  onChange: (dataUrl: string | null) => void
  height?: number
}

/** Simple canvas signature capture (mouse + touch). */
export function SignaturePad({ value, onChange, height = 160 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const drawing = useRef(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const ratio = window.devicePixelRatio || 1
    const width = canvas.clientWidth
    canvas.width = Math.floor(width * ratio)
    canvas.height = Math.floor(height * ratio)
    ctx.scale(ratio, ratio)
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.strokeStyle = '#111'
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, width, height)
    if (value) {
      const img = new Image()
      img.onload = () => ctx.drawImage(img, 0, 0, width, height)
      img.src = value
    }
  }, [height]) // eslint-disable-line react-hooks/exhaustive-deps -- redraw on mount/size only

  function pos(e: MouseEvent | TouchEvent) {
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    if ('touches' in e) {
      const t = e.touches[0]
      return { x: t.clientX - rect.left, y: t.clientY - rect.top }
    }
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  function start(e: MouseEvent | TouchEvent) {
    e.preventDefault()
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return
    drawing.current = true
    const p = pos(e)
    ctx.beginPath()
    ctx.moveTo(p.x, p.y)
  }

  function move(e: MouseEvent | TouchEvent) {
    if (!drawing.current) return
    e.preventDefault()
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return
    const p = pos(e)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
  }

  function end() {
    if (!drawing.current) return
    drawing.current = false
    const canvas = canvasRef.current
    if (canvas) onChange(canvas.toDataURL('image/png'))
  }

  function clear() {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.clientWidth, height)
    onChange(null)
  }

  return (
    <div>
      <canvas
        ref={canvasRef}
        className="signature-pad"
        style={{
          width: '100%',
          height,
          border: '1px solid #ccc',
          borderRadius: 4,
          touchAction: 'none',
          background: '#fff',
        }}
        onMouseDown={start}
        onMouseMove={move}
        onMouseUp={end}
        onMouseLeave={end}
        onTouchStart={start}
        onTouchMove={move}
        onTouchEnd={end}
      />
      <button type="button" className="btn btn-secondary btn-sm" onClick={clear}>
        Clear signature
      </button>
    </div>
  )
}
