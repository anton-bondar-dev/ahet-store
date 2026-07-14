import { useState } from 'react'

// Read-only display (supports fractional fill for averages) or interactive
// input (pass onChange). `size` in px.
export function StarRating({
  value,
  onChange,
  size = 20,
}: {
  value: number
  onChange?: (rating: number) => void
  size?: number
}) {
  const [hover, setHover] = useState<number | null>(null)
  const interactive = !!onChange
  const shown = hover ?? value

  return (
    <span className="inline-flex" role={interactive ? 'radiogroup' : 'img'}>
      {[1, 2, 3, 4, 5].map((i) => {
        // Fractional fill for read-only averages (e.g. 4.3).
        const fill = interactive
          ? shown >= i
            ? 1
            : 0
          : Math.max(0, Math.min(1, shown - (i - 1)))
        return (
          <Star
            key={i}
            fill={fill}
            size={size}
            interactive={interactive}
            onClick={() => onChange?.(i)}
            onMouseEnter={() => interactive && setHover(i)}
            onMouseLeave={() => interactive && setHover(null)}
          />
        )
      })}
    </span>
  )
}

function Star({
  fill,
  size,
  interactive,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: {
  fill: number
  size: number
  interactive: boolean
  onClick: () => void
  onMouseEnter: () => void
  onMouseLeave: () => void
}) {
  const star = (
    <svg viewBox="0 0 20 20" width={size} height={size} className="block">
      <defs>
        <linearGradient id={`sg-${fill}`}>
          <stop offset={`${fill * 100}%`} stopColor="#f59e0b" />
          <stop offset={`${fill * 100}%`} stopColor="#e5e7eb" />
        </linearGradient>
      </defs>
      <path
        d="M10 1.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L10 15.9 4.8 17.6l1-5.8L1.5 7.7l5.9-.9z"
        fill={fill >= 1 ? '#f59e0b' : fill <= 0 ? '#e5e7eb' : `url(#sg-${fill})`}
      />
    </svg>
  )
  if (!interactive) return star
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className="cursor-pointer p-0.5"
      aria-label={`${Math.round(fill)} зірок`}
    >
      {star}
    </button>
  )
}
