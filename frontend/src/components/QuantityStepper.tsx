import { useEffect, useState } from 'react'

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

  // Keep the input in sync when the server value changes (e.g. clamped).
  useEffect(() => {
    setDraft(String(value))
  }, [value])

  const clamp = (n: number) => Math.max(0, Math.min(n, max))

  const commit = (raw: string) => {
    const parsed = Number.parseInt(raw, 10)
    const next = Number.isNaN(parsed) ? 0 : clamp(parsed)
    setDraft(String(next))
    if (next !== value) onChange(next)
  }

  return (
    <div className="inline-flex items-center rounded-md border border-gray-300">
      <button
        type="button"
        onClick={() => onChange(clamp(value - 1))}
        disabled={disabled || value <= 0}
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
        onClick={() => onChange(clamp(value + 1))}
        disabled={disabled || value >= max}
        aria-label="Збільшити кількість"
        className="px-2 py-1 text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        +
      </button>
    </div>
  )
}
