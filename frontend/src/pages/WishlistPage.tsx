import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useListWishlist } from '../api/generated/wishlist/wishlist'
import { ProductCard } from '../components/ProductCard'
import { useAuth } from '../hooks/useAuth'

export function WishlistPage() {
  const navigate = useNavigate()
  const { user, isLoading: authLoading } = useAuth()

  // Wishlist is per-account: bounce anonymous visitors to login.
  useEffect(() => {
    if (!authLoading && !user) navigate('/login')
  }, [authLoading, user, navigate])

  const { data, isLoading, isError } = useListWishlist({
    query: { enabled: !!user },
  })
  const products = data?.data ?? []

  if (authLoading || !user) return <p className="p-6 text-gray-500">Завантаження…</p>

  return (
    <div className="mx-auto max-w-7xl p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Моє обране</h1>

      {isLoading ? (
        <p className="text-gray-500">Завантаження…</p>
      ) : isError ? (
        <p className="text-red-600">Не вдалося завантажити обране.</p>
      ) : products.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <div className="mb-3 text-4xl">🤍</div>
          <p className="mb-4 text-gray-500">
            У вашому списку обраного поки що порожньо.
          </p>
          <Link
            to="/"
            className="inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-700"
          >
            Перейти до каталогу
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </div>
  )
}
