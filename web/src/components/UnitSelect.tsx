import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { Field } from './ui'

const FALLBACK_UNITS = [
  'pcs',
  'pack',
  'set',
  'pair',
  'kit',
  'box',
  'roll',
  'tube',
  'bottle',
  'can',
  'drum',
  'litre',
  'ml',
  'kg',
  'g',
  'metre',
  'ft',
  'sheet',
  'filter',
]

const OTHER = '__other__'

type Props = {
  label?: string
  value: string
  onChange: (unit: string) => void
  required?: boolean
  disabled?: boolean
}

/**
 * Catalogue unit dropdown. Pick a listed unit, or choose Other… to type a custom one.
 */
export function UnitSelect({
  label = 'Unit',
  value,
  onChange,
  required,
  disabled,
}: Props) {
  const unitsQ = useQuery({
    queryKey: ['inventory-units'],
    queryFn: () => api.get<{ units: string[] }>('/api/inventory/units'),
    staleTime: 60_000,
  })
  const catalogue = useMemo(
    () => (unitsQ.data?.units?.length ? unitsQ.data.units : FALLBACK_UNITS),
    [unitsQ.data?.units],
  )

  const inCatalogue = Boolean(value) && catalogue.includes(value)
  const [useOther, setUseOther] = useState(
    () => Boolean(value) && !FALLBACK_UNITS.includes(value),
  )
  const [custom, setCustom] = useState(() =>
    value && !FALLBACK_UNITS.includes(value) ? value : '',
  )

  // Keep Other mode in sync when parent value changes (e.g. edit / autofill)
  useEffect(() => {
    if (!value) {
      setUseOther(false)
      setCustom('')
      return
    }
    if (catalogue.includes(value)) {
      setUseOther(false)
      return
    }
    setUseOther(true)
    setCustom(value)
  }, [value, catalogue])

  const selectValue = useOther || (!inCatalogue && value) ? OTHER : value || 'pcs'

  return (
    <Field label={label}>
      <select
        className="select"
        value={selectValue}
        disabled={disabled}
        required={required && !useOther}
        onChange={(e) => {
          const next = e.target.value
          if (next === OTHER) {
            setUseOther(true)
            const seed = custom || (inCatalogue ? '' : value) || ''
            setCustom(seed)
            onChange(seed)
            return
          }
          setUseOther(false)
          setCustom('')
          onChange(next)
        }}
      >
        {catalogue.map((u) => (
          <option key={u} value={u}>
            {u}
          </option>
        ))}
        <option value={OTHER}>Other…</option>
      </select>
      {useOther ? (
        <input
          type="text"
          value={custom}
          required={required}
          disabled={disabled}
          placeholder="Type custom unit"
          maxLength={20}
          style={{ marginTop: 6 }}
          onChange={(e) => {
            const raw = e.target.value.trimStart()
            setCustom(raw)
            onChange(raw.trim())
          }}
        />
      ) : null}
    </Field>
  )
}
