import { useState } from 'react'
import { Link } from 'react-router-dom'
import { productImageUrl } from '../api/http'

// Compact image slider for product cards. The current image links to the
// product page; the arrows/dots overlay it as siblings (never nested in the
// <a>) and stop the click from navigating.
export function ProductImageCarousel({
  images,
  alt,
  to,
}: {
  images: string[]
  alt: string
  to: string
}) {
  const urls = images
    .map((img) => productImageUrl(img))
    .filter((u): u is string => !!u)
  const [index, setIndex] = useState(0)
  const count = urls.length
  const safeIndex = count ? Math.min(index, count - 1) : 0

  const step = (e: React.MouseEvent, delta: number) => {
    e.preventDefault()
    e.stopPropagation()
    setIndex((i) => {
      const cur = Math.min(i, count - 1)
      return (cur + delta + count) % count
    })
  }

  const jump = (e: React.MouseEvent, i: number) => {
    e.preventDefault()
    e.stopPropagation()
    setIndex(i)
  }

  return (
    <div className="relative aspect-square overflow-hidden rounded-t-lg bg-gray-50">
      {count > 0 ? (
        <Link to={to} className="block h-full w-full">
          <img
            src={urls[safeIndex]}
            alt={alt}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        </Link>
      ) : (
        <div className="flex h-full w-full items-center justify-center text-sm text-gray-400">
          Немає зображення
        </div>
      )}

      {count > 1 && (
        <>
          <button
            type="button"
            onClick={(e) => step(e, -1)}
            aria-label="Попереднє зображення"
            className="absolute left-1.5 top-1/2 z-10 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-white/80 text-gray-700 shadow-sm ring-1 ring-gray-200 backdrop-blur transition hover:bg-white"
          >
            <Chevron dir="left" />
          </button>
          <button
            type="button"
            onClick={(e) => step(e, 1)}
            aria-label="Наступне зображення"
            className="absolute right-1.5 top-1/2 z-10 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-white/80 text-gray-700 shadow-sm ring-1 ring-gray-200 backdrop-blur transition hover:bg-white"
          >
            <Chevron dir="right" />
          </button>
          <div className="absolute inset-x-0 bottom-2 z-10 flex justify-center gap-1">
            {urls.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={(e) => jump(e, i)}
                aria-label={`Зображення ${i + 1}`}
                className={`h-1.5 rounded-full ring-1 ring-black/5 transition-all ${
                  i === safeIndex ? 'w-4 bg-white' : 'w-1.5 bg-white/60'
                }`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function Chevron({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={dir === 'left' ? 'M12 5l-5 5 5 5' : 'M8 5l5 5-5 5'} />
    </svg>
  )
}
