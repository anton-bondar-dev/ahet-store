import { Link } from 'react-router-dom'
import type { ProductOut } from '../api/generated/onlineStoreAPI.schemas'
import { productImageUrl } from '../api/http'
import { formatPrice } from '../lib/format'

export function ProductCard({
  product,
  variant = 'grid',
}: {
  product: ProductOut
  variant?: 'grid' | 'slider'
}) {
  const imageUrl = productImageUrl(product.image)
  const isUnavailable = !product.is_active || product.stock === 0
  const onSale = product.discount_price != null && product.is_active
  const isSlider = variant === 'slider'

  return (
    <Link
      to={`/product/${product.slug}`}
      className={`group relative z-10 flex h-full flex-col rounded-lg border border-gray-200 bg-white shadow-sm transition-all duration-300 hover:z-50 hover:scale-105 hover:shadow-xl ${
        isSlider ? 'overflow-hidden' : ''
      } ${isUnavailable ? 'opacity-60' : ''}`}
    >
      {isUnavailable && (
        <span className="absolute left-2 top-2 z-30 rounded bg-red-600 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-white">
          Немає в наявності
        </span>
      )}

      <div className="flex aspect-square items-center justify-center overflow-hidden rounded-t-lg bg-gray-50">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={product.title}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <span className="text-sm text-gray-400">Немає зображення</span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
          {product.category.name}
        </span>
        <h2 className="line-clamp-2 text-sm font-semibold text-gray-900">
          {product.title}
        </h2>

        <div className="mt-auto flex items-baseline gap-2 pt-2">
          {onSale ? (
            <>
              <span className="text-lg font-bold text-gray-900">
                {formatPrice(product.discount_price!)}
              </span>
              <span className="text-sm text-gray-400 line-through">
                {formatPrice(product.price)}
              </span>
            </>
          ) : (
            <span className="text-lg font-bold text-gray-900">
              {formatPrice(product.price)}
            </span>
          )}
        </div>
      </div>

      {isSlider ? (
        // Slider: overlay that slides up over the image (card is a clipping
        // container, so an expand-down panel would be cut off).
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 translate-y-full bg-white/95 p-4 text-sm text-gray-600 opacity-0 shadow-inner backdrop-blur-sm transition-all duration-300 group-hover:pointer-events-auto group-hover:translate-y-0 group-hover:opacity-100">
          <p className="line-clamp-6">{product.description}</p>
        </div>
      ) : (
        // Grid: card grows downward, revealing the description below the price.
        <div className="absolute inset-x-0 top-full z-20 max-h-0 overflow-hidden rounded-b-lg border-x border-b border-gray-200 bg-white opacity-0 shadow-xl transition-all duration-300 group-hover:max-h-40 group-hover:opacity-100">
          <p className="p-4 text-sm text-gray-600">{product.description}</p>
        </div>
      )}
    </Link>
  )
}
