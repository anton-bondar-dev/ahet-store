import { useListProducts } from './api/generated/catalog/catalog'

function App() {
  const { data, isLoading, isError, error } = useListProducts()

  if (isLoading) return <p>Loading products…</p>
  if (isError) return <p>Failed to load products: {String(error)}</p>

  const products = data?.data ?? []

  return (
    <main style={{ maxWidth: 640, margin: '2rem auto', fontFamily: 'system-ui' }}>
      <h1>Products</h1>
      {products.length === 0 ? (
        <p>No products yet.</p>
      ) : (
        <ul>
          {products.map((product) => (
            <li key={product.id}>
              <strong>{product.title}</strong> — {product.category.name} — ${product.price}
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}

export default App
