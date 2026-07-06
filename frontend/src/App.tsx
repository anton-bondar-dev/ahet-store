import { useListProducts } from './api/generated/catalog/catalog'
import { ProductCard } from './components/ProductCard'

function App() {
  const { data, isLoading, isError, error } = useListProducts()

  if (isLoading) {
    return <p className="p-6 text-gray-500">Loading products…</p>
  }
  if (isError) {
    return <p className="p-6 text-red-600">Failed to load products: {String(error)}</p>
  }

  const products = data?.data ?? []

  return (
    <main className="mx-auto max-w-7xl p-6">
      <h1 className="mb-6 text-3xl font-bold text-gray-900">Products</h1>
      {products.length === 0 ? (
        <p className="text-gray-500">No products yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </main>
  )
}

export default App
