import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useGetProduct } from '../api/generated/catalog/catalog'
import { Breadcrumbs, type Crumb } from '../components/Breadcrumbs'
import { ProductGallery } from '../components/ProductGallery'
import { ReviewsSection } from '../components/reviews/ReviewsSection'
import { WishlistButton } from '../components/WishlistButton'
import { useCart } from '../hooks/useCart'
import { useIsStaff } from '../hooks/useIsStaff'
import { useRecentlyViewed } from '../hooks/useRecentlyViewed'
import { formatPrice } from '../lib/format'

export function ProductDetail() {
  const { slug } = useParams<{ slug: string }>()
  const isStaff = useIsStaff()
  const { data, isLoading, isError } = useGetProduct(slug ?? '', {
    query: { enabled: !!slug },
  })

  const product = data?.data
  const { record } = useRecentlyViewed()
  const recordedId = useRef<number | null>(null)

  // Record the view once per product (logged-in → backend, else localStorage).
  const productId = product?.id
  useEffect(() => {
    if (productId && recordedId.current !== productId) {
      recordedId.current = productId
      record(productId)
    }
  }, [productId, record])

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

  const galleryImages =
    product.images && product.images.length > 0
      ? product.images
      : product.image
        ? [product.image]
        : []
  const inStock = product.is_active && product.stock > 0
  const onSale = product.discount_price != null && product.is_active

  const crumbs: Crumb[] = [
    { label: 'Головна', to: '/' },
    // Full ancestral path (root → parent), then the leaf category, then self.
    ...(product.category.ancestors ?? []).map((ancestor) => ({
      label: ancestor.name,
      to: `/?categoryId=${ancestor.id}`,
    })),
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
        {/* Image gallery / slider */}
        <div className="md:w-1/2">
          <ProductGallery images={galleryImages} alt={product.title} />
        </div>

        {/* Details */}
        <div className="flex flex-col gap-4 md:w-1/2">
          <h1 className="text-2xl font-bold text-gray-900">{product.title}</h1>

          <div className="flex items-baseline gap-3">
            {onSale ? (
              <>
                <span className="text-3xl font-extrabold tracking-tight text-brand">
                  {formatPrice(product.discount_price!)}
                </span>
                <span className="text-lg text-gray-400 line-through">
                  {formatPrice(product.price)}
                </span>
              </>
            ) : (
              <span className="text-3xl font-extrabold tracking-tight text-gray-900">
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

          {!isStaff && (
            <div className="flex items-center gap-3">
              <AddToCartButton productId={product.id} disabled={!inStock} />
              <WishlistButton productId={product.id} size="lg" />
            </div>
          )}

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

      <ReviewsSection
        productId={product.id}
        slug={product.slug}
        averageRating={product.average_rating}
        reviewsCount={product.reviews_count}
      />
    </div>
  )
}

function AddToCartButton({
  productId,
  disabled,
}: {
  productId: number
  disabled: boolean
}) {
  const { addToCart, isAdding } = useCart()
  const [added, setAdded] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleClick = () => {
    addToCart(productId)
      .then(() => {
        setAdded(true)
        if (timerRef.current) clearTimeout(timerRef.current)
        timerRef.current = setTimeout(() => setAdded(false), 2000)
      })
      .catch(() => {
        /* keep the button in its normal state on failure */
      })
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || isAdding}
      className={`w-fit rounded-md px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
        added ? 'bg-green-600' : 'bg-brand hover:bg-brand-dark'
      }`}
    >
      {disabled ? 'Немає в наявності' : added ? 'Додано!' : 'У кошик'}
    </button>
  )
}

// Terminal breadcrumb: shows the product title as a button that copies the
// current page URL. Copying is a deliberate two-step: the first click only
// warns that the next click will copy; the second click performs the copy.
function CopyLinkCrumb({ title }: { title: string }) {
  const [mode, setMode] = useState<'idle' | 'warn' | 'copied'>('idle')
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
    timerRef.current = setTimeout(() => setMode('idle'), 3000)
  }

  useEffect(() => clearTimer, [])

  const handleClick = () => {
    if (mode === 'warn') {
      // Second click confirms the warning → actually copy now.
      navigator.clipboard
        .writeText(window.location.href)
        .then(() => {
          setMode('copied')
          scheduleHide()
        })
        .catch(() => {
          // Clipboard unavailable (e.g. insecure context) — drop the prompt.
          setMode('idle')
        })
    } else {
      // First click only arms + warns; nothing is copied yet.
      setMode('warn')
      scheduleHide()
    }
  }

  const isWarn = mode === 'warn'
  const bg = isWarn ? 'bg-amber-600' : 'bg-gray-900'

  return (
    <span className="relative">
      <button
        type="button"
        onClick={handleClick}
        title={title}
        className="max-w-xs truncate text-gray-700 transition hover:text-gray-900"
      >
        {title}
      </button>

      {mode !== 'idle' && (
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
          className={`absolute left-0 top-full z-20 mt-3 flex w-64 items-start gap-2 rounded-lg px-3 py-2 text-xs text-white shadow-lg ${bg} ${
            hovered ? '' : 'animate-float'
          }`}
        >
          {/* pointer/arrow */}
          <span className={`absolute -top-1 left-6 h-2 w-2 rotate-45 ${bg}`} />
          <span className="flex-1 leading-relaxed">
            {isWarn
              ? 'Наступний клік скопіює посилання на товар у буфер обміну.'
              : 'Посилання на товар скопійовано в буфер обміну!'}
          </span>
          <button
            type="button"
            onClick={() => {
              clearTimer()
              setMode('idle')
            }}
            aria-label="Закрити"
            className="shrink-0 text-white/70 transition hover:text-white"
          >
            ✕
          </button>
        </div>
      )}
    </span>
  )
}
