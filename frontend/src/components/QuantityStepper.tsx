import { useEffect, useRef, useState } from 'react'

// Shared [<] [input] [>] control. Accepts min 0, max = stock; commits clamped
// values via onChange. Local input state lets the user type freely before commit.
export function QuantityStepper({
  value,
  max,
  onChange,
  disabled,
}: {
  value: number
  max: number
  onChange: (quantity: number) => void
  disabled?: boolean
}) {
  const [draft, setDraft] = useState(String(value))
  // `shown` drives the button disabled-state; `latest` is the authoritative
  // quantity used for +/- so rapid clicks accumulate instead of all reading the
  // same (still-loading) server value and collapsing into one step.
  const [shown, setShown] = useState(value)
  const latest = useRef(value)

  // Reconcile with the server value when it changes (e.g. clamped to stock).
  useEffect(() => {
    latest.current = value
    setShown(value)
    setDraft(String(value))
  }, [value])

  const clamp = (n: number) => Math.max(0, Math.min(n, max))

  const step = (delta: number) => {
    const next = clamp(latest.current + delta)
    if (next === latest.current) return
    latest.current = next
    setShown(next)
    setDraft(String(next))
    onChange(next)
  }

  const commit = (raw: string) => {
    const parsed = Number.parseInt(raw, 10)
    const next = Number.isNaN(parsed) ? 0 : clamp(parsed)
    latest.current = next
    setShown(next)
    setDraft(String(next))
    if (next !== value) onChange(next)
  }

  return (
    <div className="inline-flex items-center rounded-md border border-gray-300">
      <button
        type="button"
        onClick={() => step(-1)}
        disabled={disabled || shown <= 0}
        aria-label="Зменшити кількість"
        className="px-2 py-1 text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        –
      </button>
      <input
        type="number"
        min={0}
        max={max}
        value={draft}
        disabled={disabled}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        }}
        aria-label="Кількість"
        className="w-12 border-x border-gray-300 py-1 text-center text-sm text-gray-900 focus:outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
      />
      <button
        type="button"
        onClick={() => step(1)}
        disabled={disabled || shown >= max}
        aria-label="Збільшити кількість"
        className="px-2 py-1 text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        +
      </button>
    </div>
  )
}
