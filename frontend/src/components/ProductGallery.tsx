import { useState } from 'react'
import { productImageUrl } from '../api/http'

// Product-page gallery: a large main image with prev/next arrows and a
// clickable thumbnail strip beneath it.
export function ProductGallery({
  images,
  alt,
}: {
  images: string[]
  alt: string
}) {
  const urls = images
    .map((img) => productImageUrl(img))
    .filter((u): u is string => !!u)
  const [index, setIndex] = useState(0)
  const count = urls.length
  const safeIndex = count ? Math.min(index, count - 1) : 0

  const step = (delta: number) =>
    setIndex((i) => {
      const cur = Math.min(i, count - 1)
      return (cur + delta + count) % count
    })

  return (
    <div className="flex flex-col gap-3">
      <div className="relative flex aspect-square items-center justify-center overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
        {count > 0 ? (
          <img
            src={urls[safeIndex]}
            alt={alt}
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="text-sm text-gray-400">Немає зображення</span>
        )}

        {count > 1 && (
          <>
            <button
              type="button"
              onClick={() => step(-1)}
              aria-label="Попереднє зображення"
              className="absolute left-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/85 text-gray-700 shadow ring-1 ring-gray-200 backdrop-blur transition hover:bg-white"
            >
              <Chevron dir="left" />
            </button>
            <button
              type="button"
              onClick={() => step(1)}
              aria-label="Наступне зображення"
              className="absolute right-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/85 text-gray-700 shadow ring-1 ring-gray-200 backdrop-blur transition hover:bg-white"
            >
              <Chevron dir="right" />
            </button>
            <span className="absolute bottom-2 right-2 rounded-full bg-black/55 px-2 py-0.5 text-xs font-medium text-white">
              {safeIndex + 1}/{count}
            </span>
          </>
        )}
      </div>

      {count > 1 && (
        <div className="flex gap-2 overflow-x-auto scrollbar-hide">
          {urls.map((url, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Зображення ${i + 1}`}
              aria-current={i === safeIndex}
              className={`aspect-square w-16 shrink-0 overflow-hidden rounded-md border-2 transition ${
                i === safeIndex
                  ? 'border-gray-900'
                  : 'border-transparent hover:border-gray-300'
              }`}
            >
              <img src={url} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Chevron({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className="h-5 w-5"
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
