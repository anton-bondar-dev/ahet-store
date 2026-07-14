import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useListCategories,
  useListProducts,
} from './api/generated/catalog/catalog'
import type { ProductOut } from './api/generated/onlineStoreAPI.schemas'
import { ProductCard } from './components/ProductCard'

type SortKey = 'newest' | 'price-asc' | 'price-desc' | 'discount'

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'newest', label: 'Спочатку нові' },
  { value: 'price-asc', label: 'Ціна: за зростанням' },
  { value: 'price-desc', label: 'Ціна: за спаданням' },
  { value: 'discount', label: 'Найбільша знижка' },
]

function effectivePrice(product: ProductOut): number {
  return Number(product.discount_price ?? product.price)
}

function discountAmount(product: ProductOut): number {
  if (product.discount_price == null) return 0
  return Number(product.price) - Number(product.discount_price)
}

function sortProducts(products: ProductOut[], sortBy: SortKey): ProductOut[] {
  const sorted = [...products]
  switch (sortBy) {
    case 'price-asc':
      sorted.sort((a, b) => effectivePrice(a) - effectivePrice(b))
      break
    case 'price-desc':
      sorted.sort((a, b) => effectivePrice(b) - effectivePrice(a))
      break
    case 'discount':
      sorted.sort((a, b) => discountAmount(b) - discountAmount(a))
      break
    case 'newest':
    default:
      // No created_at on the model; id descending is the recency proxy.
      sorted.sort((a, b) => b.id - a.id)
      break
  }
  return sorted
}

function App() {
  const [searchParams, setSearchParams] = useSearchParams()
  const query = (searchParams.get('q') ?? '').trim()

  const productsQuery = useListProducts()
  const categoriesQuery = useListCategories()
  const searchQuery = useListProducts(
    { q: query },
    { query: { enabled: query.length > 0 } },
  )

  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(
    () => {
      const raw = searchParams.get('categoryId')
      const id = raw ? Number(raw) : NaN
      return Number.isInteger(id) ? id : null
    },
  )
  const [sortBy, setSortBy] = useState<SortKey>('newest')

  const selectCategory = (id: number | null) => {
    setSelectedCategoryId(id)
    // Leaving search mode when the user starts browsing categories.
    if (query) {
      setSearchParams(
        (prev) => {
          prev.delete('q')
          return prev
        },
        { replace: true },
      )
    }
  }

  if (productsQuery.isLoading || categoriesQuery.isLoading) {
    return <p className="p-6 text-gray-500">Завантаження товарів…</p>
  }
  if (productsQuery.isError || categoriesQuery.isError) {
    const err = productsQuery.error ?? categoriesQuery.error
    return (
      <p className="p-6 text-red-600">
        Не вдалося завантажити товари: {String(err)}
      </p>
    )
  }

  const products = productsQuery.data?.data ?? []
  const categories = categoriesQuery.data?.data ?? []

  const countByCategory = new Map<number, number>()
  for (const product of products) {
    countByCategory.set(
      product.category.id,
      (countByCategory.get(product.category.id) ?? 0) + 1,
    )
  }

  return (
    <div className="mx-auto flex max-w-7xl gap-8 p-6">
      <aside className="w-56 shrink-0">
        <nav className="flex flex-col gap-1">
          <CategoryItem
            name="Усі товари"
            count={products.length}
            active={!query && selectedCategoryId === null}
            onClick={() => selectCategory(null)}
          />
          {categories.map((category) => (
            <CategoryItem
              key={category.id}
              name={category.name}
              count={countByCategory.get(category.id) ?? 0}
              active={!query && selectedCategoryId === category.id}
              onClick={() => selectCategory(category.id)}
            />
          ))}
        </nav>
      </aside>

      <main className="min-w-0 flex-1">
        {query ? (
          <SearchResults query={query} search={searchQuery} />
        ) : (
          <>
            <div className="mb-6 flex items-center justify-end">
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <span>Сортування</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as SortKey)}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 shadow-sm focus:border-gray-500 focus:outline-none"
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {selectedCategoryId === null ? (
              <AllProductsView
                products={products}
                categories={categories}
                sortBy={sortBy}
              />
            ) : (
              <CategoryGrid
                products={sortProducts(
                  products.filter((p) => p.category.id === selectedCategoryId),
                  sortBy,
                )}
              />
            )}
          </>
        )}
      </main>
    </div>
  )
}

function CategoryItem({
  name,
  count,
  active,
  onClick,
}: {
  name: string
  count: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center justify-between rounded-md px-3 py-2 text-left text-sm transition ${
        active
          ? 'bg-gray-100 font-semibold text-gray-900'
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
      }`}
    >
      <span className="truncate">{name}</span>
      <span className="ml-2 shrink-0 text-xs text-gray-400">{count}</span>
    </button>
  )
}

function AllProductsView({
  products,
  categories,
  sortBy,
}: {
  products: ProductOut[]
  categories: { id: number; name: string }[]
  sortBy: SortKey
}) {
  const sections = categories
    .map((category) => ({
      category,
      items: sortProducts(
        products.filter((p) => p.category.id === category.id),
        sortBy,
      ),
    }))
    .filter((section) => section.items.length > 0)

  if (sections.length === 0) {
    return <p className="text-gray-500">Товарів поки немає.</p>
  }

  return (
    <div className="flex flex-col gap-6">
      {sections.map(({ category, items }) => (
        <section key={category.id}>
          <h2 className="mb-4 text-xl font-semibold text-gray-900">
            {category.name}
          </h2>
          <div className="flex snap-x gap-6 overflow-x-auto overflow-y-hidden scrollbar-hide py-4">
            {items.map((product) => (
              <div key={product.id} className="w-64 shrink-0 snap-start">
                <ProductCard product={product} />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function SearchResults({
  query,
  search,
}: {
  query: string
  search: {
    data?: { data: ProductOut[] }
    isLoading: boolean
    isError: boolean
  }
}) {
  const results = search.data?.data ?? []

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-gray-900">
        Результати пошуку: «{query}»
      </h1>
      <p className="mb-6 text-sm text-gray-500">
        {search.isLoading
          ? 'Пошук…'
          : `Знайдено товарів: ${results.length}`}
      </p>

      {search.isError ? (
        <p className="text-red-600">Не вдалося виконати пошук.</p>
      ) : search.isLoading ? null : results.length === 0 ? (
        <p className="text-gray-500">Нічого не знайдено.</p>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {results.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </div>
  )
}

function CategoryGrid({ products }: { products: ProductOut[] }) {
  if (products.length === 0) {
    return <p className="text-gray-500">У цій категорії немає товарів.</p>
  }
  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  )
}

export default App
