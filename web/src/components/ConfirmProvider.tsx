import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { Dialog } from './ui'

type ConfirmOpts = {
  title?: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}

type PromptOpts = {
  title?: string
  message: string
  defaultValue?: string
  placeholder?: string
  confirmLabel?: string
  cancelLabel?: string
  /** When true, empty input cannot continue */
  required?: boolean
}

type ConfirmApi = {
  confirm: (opts: ConfirmOpts | string) => Promise<boolean>
  prompt: (opts: PromptOpts | string) => Promise<string | null>
}

const ConfirmContext = createContext<ConfirmApi | null>(null)

type Mode =
  | { kind: 'confirm'; opts: ConfirmOpts; resolve: (v: boolean) => void }
  | { kind: 'prompt'; opts: PromptOpts; resolve: (v: string | null) => void }
  | null

function normalizeConfirm(opts: ConfirmOpts | string): ConfirmOpts {
  return typeof opts === 'string' ? { message: opts } : opts
}

function normalizePrompt(opts: PromptOpts | string): PromptOpts {
  return typeof opts === 'string' ? { message: opts } : opts
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(null)
  const [text, setText] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const titleId = useId()

  const close = useCallback(() => setMode(null), [])

  const confirm = useCallback((opts: ConfirmOpts | string) => {
    return new Promise<boolean>((resolve) => {
      setMode({ kind: 'confirm', opts: normalizeConfirm(opts), resolve })
    })
  }, [])

  const prompt = useCallback((opts: PromptOpts | string) => {
    const n = normalizePrompt(opts)
    return new Promise<string | null>((resolve) => {
      setText(n.defaultValue || '')
      setMode({ kind: 'prompt', opts: n, resolve })
    })
  }, [])

  useEffect(() => {
    if (mode?.kind === 'prompt') {
      const t = window.setTimeout(() => inputRef.current?.focus(), 20)
      return () => window.clearTimeout(t)
    }
  }, [mode])

  useEffect(() => {
    if (!mode) return
    const current = mode
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return
      e.preventDefault()
      if (current.kind === 'confirm') current.resolve(false)
      else current.resolve(null)
      close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mode, close])

  function cancel() {
    if (!mode) return
    if (mode.kind === 'confirm') mode.resolve(false)
    else mode.resolve(null)
    close()
  }

  function accept() {
    if (!mode) return
    if (mode.kind === 'confirm') {
      mode.resolve(true)
      close()
      return
    }
    const value = text.trim()
    if (mode.opts.required !== false && !value) return
    mode.resolve(value)
    close()
  }

  const open = Boolean(mode)
  const title =
    mode?.kind === 'confirm'
      ? mode.opts.title || (mode.opts.danger ? 'Confirm delete' : 'Please confirm')
      : mode?.kind === 'prompt'
        ? mode.opts.title || 'Input required'
        : ''
  const message = mode?.opts.message || ''
  const confirmLabel =
    mode?.kind === 'confirm'
      ? mode.opts.confirmLabel || (mode.opts.danger ? 'Delete' : 'Continue')
      : mode?.kind === 'prompt'
        ? mode.opts.confirmLabel || 'Continue'
        : 'Continue'
  const cancelLabel = mode?.opts.cancelLabel || 'Cancel'
  const danger = mode?.kind === 'confirm' ? Boolean(mode.opts.danger) : false

  return (
    <ConfirmContext.Provider value={{ confirm, prompt }}>
      {children}
      <Dialog open={open} title={title} onClose={cancel}>
        <p id={titleId} style={{ marginBottom: 16 }}>
          {message}
        </p>
        {mode?.kind === 'prompt' ? (
          <input
            ref={inputRef}
            className="input"
            value={text}
            placeholder={mode.opts.placeholder}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                accept()
              }
            }}
            style={{ marginBottom: 16 }}
          />
        ) : null}
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={cancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? 'btn btn-danger' : 'btn'}
            onClick={accept}
            disabled={
              mode?.kind === 'prompt' &&
              mode.opts.required !== false &&
              !text.trim()
            }
          >
            {confirmLabel}
          </button>
        </div>
      </Dialog>
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): ConfirmApi {
  const ctx = useContext(ConfirmContext)
  if (!ctx) {
    throw new Error('useConfirm must be used within ConfirmProvider')
  }
  return ctx
}
