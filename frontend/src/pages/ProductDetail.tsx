import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useGetProduct } from '../api/generated/catalog/catalog'
import { productImageUrl } from '../api/http'
import { formatPrice } from '../lib/format'

type Crumb = { label: string; to?: string; node?: ReactNode }

export function ProductDetail() {
  const { slug } = useParams<{ slug: string }>()
  const { data, isLoading, isError } = useGetProduct(slug ?? '', {
    query: { enabled: !!slug },
  })

  const product = data?.data

  if (isLoading) {
    return <p className="p-6 text-gray-500">Завантаження товару…</p>
  }
  if (isError || !product) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Breadcrumbs crumbs={[{ label: 'Головна', to: '/' }]} />
        <p className="mt-6 text-red-600">Товар не знайдено.</p>
      </div>
    )
  }

  const imageUrl = productImageUrl(product.image)
  const inStock = product.is_active && product.stock > 0
  const onSale = product.discount_price != null && product.is_active

  const crumbs: Crumb[] = [
    { label: 'Головна', to: '/' },
    {
      label: product.category.name,
      to: `/?categoryId=${product.category.id}`,
    },
    { label: product.title, node: <CopyLinkCrumb title={product.title} /> },
  ]

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs crumbs={crumbs} />

      <div className="mt-6 flex flex-col gap-8 md:flex-row">
        {/* Image */}
        <div className="md:w-1/2">
          <div className="flex aspect-square items-center justify-center overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
            {imageUrl ? (
              <img
                src={imageUrl}
                alt={product.title}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="text-sm text-gray-400">Немає зображення</span>
            )}
          </div>
        </div>

        {/* Details */}
        <div className="flex flex-col gap-4 md:w-1/2">
          <h1 className="text-2xl font-bold text-gray-900">{product.title}</h1>

          <div className="flex items-baseline gap-3">
            {onSale ? (
              <>
                <span className="text-3xl font-bold text-gray-900">
                  {formatPrice(product.discount_price!)}
                </span>
                <span className="text-lg text-gray-400 line-through">
                  {formatPrice(product.price)}
                </span>
              </>
            ) : (
              <span className="text-3xl font-bold text-gray-900">
                {formatPrice(product.price)}
              </span>
            )}
          </div>

          <span
            className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-sm font-medium ${
              inStock ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}
          >
            {inStock ? 'В наявності' : 'Немає в наявності'}
          </span>

          {product.description && (
            <div className="border-t border-gray-100 pt-4">
              <h2 className="mb-2 text-sm font-semibold text-gray-900">
                Опис
              </h2>
              <p className="whitespace-pre-line text-sm leading-relaxed text-gray-600">
                {product.description}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Навігаційний ланцюжок">
      <ol className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1
          return (
            <li key={index} className="flex min-w-0 items-center gap-2">
              {index > 0 && <span className="text-gray-300">/</span>}
              {crumb.node ? (
                crumb.node
              ) : crumb.to ? (
                <Link to={crumb.to} className="transition hover:text-gray-900">
                  {crumb.label}
                </Link>
              ) : (
                <span
                  className={`truncate ${isLast ? 'max-w-xs text-gray-700' : ''}`}
                  title={crumb.label}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {crumb.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

// Terminal breadcrumb: shows the product title as a button that copies the
// current page URL, with a dismissible, hover-persistent floating tooltip.
function CopyLinkCrumb({ title }: { title: string }) {
  const [copied, setCopied] = useState(false)
  const [hovered, setHovered] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  const scheduleHide = () => {
    clearTimer()
    timerRef.current = setTimeout(() => setCopied(false), 3000)
  }

  useEffect(() => clearTimer, [])

  const handleCopy = () => {
    navigator.clipboard
      .writeText(window.location.href)
      .then(() => {
        setCopied(true)
        scheduleHide()
      })
      .catch(() => {
        /* clipboard unavailable (e.g. insecure context) — no-op */
      })
  }

  return (
    <span className="relative">
      <button
        type="button"
        onClick={handleCopy}
        title={title}
        className="max-w-xs truncate text-gray-700 transition hover:text-gray-900"
      >
        {title}
      </button>

      {copied && (
        <div
          role="status"
          onMouseEnter={() => {
            setHovered(true)
            clearTimer()
          }}
          onMouseLeave={() => {
            setHovered(false)
            scheduleHide()
          }}
          className={`absolute left-0 top-full z-20 mt-3 flex w-64 items-start gap-2 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg ${
            hovered ? '' : 'animate-float'
          }`}
        >
          {/* pointer/arrow */}
          <span className="absolute -top-1 left-6 h-2 w-2 rotate-45 bg-gray-900" />
          <span className="flex-1 leading-relaxed">
            Посилання на товар скопійовано в буфер обміну!
          </span>
          <button
            type="button"
            onClick={() => {
              clearTimer()
              setCopied(false)
            }}
            aria-label="Закрити"
            className="shrink-0 text-gray-400 transition hover:text-white"
          >
            ✕
          </button>
        </div>
      )}
    </span>
  )
}
