import { useEffect, useId, useRef, useState } from 'react'
import {
  searchEntities,
  type EntityHit,
  type EntityType,
} from '../api/entities'
import { Field } from './ui'

type Props = {
  label: string
  type: EntityType
  valueId?: number | null
  displayValue?: string
  placeholder?: string
  customerId?: number | null
  required?: boolean
  disabled?: boolean
  onSelect: (hit: EntityHit | null) => void
}

/**
 * Searchable entity selector. Staff type to search; pick once — other modules
 * reuse the same permanent id via onSelect.
 */
export function EntitySelect({
  label,
  type,
  valueId,
  displayValue = '',
  placeholder = 'Type to search…',
  customerId,
  required,
  disabled,
  onSelect,
}: Props) {
  const listId = useId()
  const [text, setText] = useState(displayValue)
  const [hits, setHits] = useState<EntityHit[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setText(displayValue)
  }, [displayValue, valueId])

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  function runSearch(q: string) {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      setLoading(true)
      setHint(null)
      try {
        const data = await searchEntities(type, q, {
          limit: 15,
          customerId: customerId ?? undefined,
        })
        setHits(data.results || [])
        setOpen(true)
        if (!(data.results || []).length && data.did_you_mean) {
          setHint(`Did you mean “${data.did_you_mean}”?`)
        } else if (!(data.results || []).length && data.closest?.length) {
          setHint(`Closest: ${data.closest.slice(0, 3).join(', ')}`)
        }
      } catch (err) {
        setHits([])
        setHint(err instanceof Error ? err.message : 'Search failed')
      } finally {
        setLoading(false)
      }
    }, 220)
  }

  function pick(hit: EntityHit) {
    setText(hit.label)
    setOpen(false)
    setHits([])
    onSelect(hit)
  }

  function clear() {
    setText('')
    setHits([])
    onSelect(null)
  }

  return (
    <Field label={label}>
      <div className="entity-select" ref={wrapRef}>
        <div className="entity-select-row">
          <input
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            required={required}
            disabled={disabled}
            value={text}
            placeholder={placeholder}
            onChange={(e) => {
              const v = e.target.value
              setText(v)
              if (!v) {
                onSelect(null)
                setHits([])
                setOpen(false)
                return
              }
              runSearch(v)
            }}
            onFocus={() => {
              if (!hits.length) runSearch(text || '')
              else setOpen(true)
            }}
          />
          {valueId || text ? (
            <button type="button" className="btn btn-secondary btn-sm" onClick={clear}>
              Clear
            </button>
          ) : null}
        </div>
        {loading ? <p className="muted entity-select-hint">Searching…</p> : null}
        {hint && !loading ? <p className="muted entity-select-hint">{hint}</p> : null}
        {valueId ? (
          <p className="muted entity-select-hint">Selected id #{valueId}</p>
        ) : null}
        {open && hits.length > 0 ? (
          <ul id={listId} className="entity-select-list" role="listbox">
            {hits.map((h) => (
              <li key={h.id}>
                <button type="button" role="option" onClick={() => pick(h)}>
                  {h.label}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {open && !loading && text && hits.length === 0 ? (
          <p className="muted entity-select-hint">No matches — create a new record or refine search.</p>
        ) : null}
      </div>
    </Field>
  )
}
