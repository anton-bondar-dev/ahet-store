import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGetSuggestions } from '../api/generated/catalog/catalog'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useSearchHistory } from '../hooks/useSearchHistory'

const MAX_RECENT = 5
const MAX_SUGGESTIONS = 10

export function SearchBar() {
  const navigate = useNavigate()
  const { history, addSearch } = useSearchHistory()

  const [value, setValue] = useState('')
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const debounced = useDebouncedValue(value.trim(), 250)
  const { data: suggestionsResp } = useGetSuggestions(
    { q: debounced },
    { query: { enabled: open && debounced.length >= 1 } },
  )

  // Close the dropdown when clicking outside the search container.
  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

  const recent = (
    value.trim()
      ? history.filter((h) => h.toLowerCase().includes(value.trim().toLowerCase()))
      : history
  ).slice(0, MAX_RECENT)

  const suggestions = (suggestionsResp?.data ?? []).slice(0, MAX_SUGGESTIONS)

  const submit = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    addSearch(trimmed)
    setValue(trimmed)
    setOpen(false)
    navigate(`/?q=${encodeURIComponent(trimmed)}`)
  }

  const showDropdown = open && (recent.length > 0 || suggestions.length > 0)

  return (
    <div ref={containerRef} className="relative max-w-md flex-1">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit(value)
        }}
      >
        <svg
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <circle cx="9" cy="9" r="6" />
          <path d="m14 14 4 4" strokeLinecap="round" />
        </svg>
        <input
          type="search"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false)
          }}
          placeholder="Пошук товарів…"
          aria-label="Пошук товарів"
          className="w-full rounded-md border border-gray-300 bg-gray-50 py-2 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-500 focus:bg-white focus:outline-none"
        />
      </form>

      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 overflow-hidden rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
          {recent.length > 0 && (
            <div>
              <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
                Нещодавні
              </p>
              {recent.map((item) => (
                <button
                  key={`recent-${item}`}
                  type="button"
                  // onMouseDown (before input blur) so the click registers reliably.
                  onMouseDown={(e) => {
                    e.preventDefault()
                    submit(item)
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  <svg
                    className="h-4 w-4 shrink-0 text-gray-400"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 7v5l3 2" />
                  </svg>
                  <span className="truncate">{item}</span>
                </button>
              ))}
            </div>
          )}

          {suggestions.length > 0 && (
            <div>
              <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
                Підказки
              </p>
              {suggestions.map((s) => (
                <button
                  key={`sug-${s.type}-${s.text}`}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    submit(s.text)
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  <svg
                    className="h-4 w-4 shrink-0 text-gray-400"
                    viewBox="0 0 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <circle cx="9" cy="9" r="6" />
                    <path d="m14 14 4 4" strokeLinecap="round" />
                  </svg>
                  <span className="truncate">{s.text}</span>
                  {s.type === 'category' && (
                    <span className="ml-auto shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                      категорія
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
