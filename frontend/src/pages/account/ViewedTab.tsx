import { useGetViewed } from '../../api/generated/products/products'
import { ProductCard } from '../../components/ProductCard'

export function ViewedTab() {
  const { data, isLoading, isError } = useGetViewed()
  const products = data?.data ?? []

  if (isLoading) return <p className="text-gray-500">Завантаження…</p>
  if (isError) return <p className="text-red-600">Не вдалося завантажити історію.</p>

  return (
    <div>
      <h2 className="mb-5 text-lg font-semibold text-gray-900">Історія переглядів</h2>
      {products.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center">
          <p className="text-gray-500">Ви ще не переглядали товари.</p>
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
