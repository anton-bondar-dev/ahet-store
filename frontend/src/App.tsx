import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useListCategories,
  useListProducts,
} from './api/generated/catalog/catalog'
import type {
  CategoryOut,
  ProductOut,
} from './api/generated/onlineStoreAPI.schemas'
import { Breadcrumbs, type Crumb } from './components/Breadcrumbs'
import { CategoryTree } from './components/CategoryTree'
import { ProductCard } from './components/ProductCard'
import { buildCategoryTree, subtreeCounts } from './lib/categoryTree'

type SortKey = 'newest' | 'popular' | 'price-asc' | 'price-desc' | 'discount'

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'newest', label: 'Спочатку нові' },
  { value: 'popular', label: 'За популярністю' },
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

  const [sortBy, setSortBy] = useState<SortKey>('newest')
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(
    () => {
      const raw = searchParams.get('categoryId')
      const id = raw ? Number(raw) : NaN
      return Number.isInteger(id) ? id : null
    },
  )
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  // Store-wide popularity ranking (Trending Engine) for the "all products" view.
  const popularQuery = useListProducts(
    { sort: 'popular' },
    {
      query: {
        enabled:
          sortBy === 'popular' &&
          query.length === 0 &&
          selectedCategoryId === null,
      },
    },
  )

  // Products for the selected category — the API cascades to the whole subtree.
  // Popularity is server-ordered; other sorts are applied client-side below.
  const categoryQuery = useListProducts(
    {
      category: selectedCategoryId ?? undefined,
      sort: sortBy === 'popular' ? 'popular' : undefined,
    },
    { query: { enabled: selectedCategoryId != null && query.length === 0 } },
  )

  // Auto-expand the path to the selected category (e.g. arriving via a deep
  // link or a product-page breadcrumb) so its place in the tree is visible.
  useEffect(() => {
    if (selectedCategoryId == null) return
    const cats = categoriesQuery.data?.data ?? []
    const selected = cats.find((c) => c.id === selectedCategoryId)
    if (!selected) return
    setExpanded((prev) => {
      const next = new Set(prev)
      next.add(selected.id)
      for (const ancestor of selected.ancestors ?? []) next.add(ancestor.id)
      return next
    })
  }, [selectedCategoryId, categoriesQuery.data])

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
  const tree = buildCategoryTree(categories)
  const counts = subtreeCounts(products)
  const selectedCategory = categories.find((c) => c.id === selectedCategoryId)

  // Popularity ranking (product id → global position) for the "all products"
  // grouped view, so sections stay category-grouped while ordered by popularity.
  const popularRank = new Map(
    (popularQuery.data?.data ?? []).map((p, i) => [p.id, i] as const),
  )
  const byPopularity = (a: ProductOut, b: ProductOut) =>
    (popularRank.get(a.id) ?? Infinity) - (popularRank.get(b.id) ?? Infinity)

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

  const toggleExpand = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  // Breadcrumb trail for the selected category: Усі товари / …ancestors / self.
  const categoryCrumbs: Crumb[] = selectedCategory
    ? [
        { label: 'Усі товари', onClick: () => selectCategory(null) },
        ...(selectedCategory.ancestors ?? []).map((a) => ({
          label: a.name,
          onClick: () => selectCategory(a.id),
        })),
        { label: selectedCategory.name },
      ]
    : []

  const categoryProducts = categoryQuery.data?.data ?? []
  const sortedCategoryProducts =
    sortBy === 'popular'
      ? categoryProducts
      : sortProducts(categoryProducts, sortBy)

  return (
    <div className="mx-auto flex max-w-7xl gap-8 p-6">
      <aside className="w-64 shrink-0">
        <nav className="flex flex-col gap-1">
          <button
            type="button"
            onClick={() => selectCategory(null)}
            className={`flex items-center justify-between rounded-md px-3 py-2 text-left text-sm transition ${
              !query && selectedCategoryId === null
                ? 'bg-gray-100 font-semibold text-gray-900'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <span className="truncate">Усі товари</span>
            <span className="ml-2 shrink-0 text-xs text-gray-400">
              {products.length}
            </span>
          </button>

          <CategoryTree
            nodes={tree}
            selectedId={query ? null : selectedCategoryId}
            expanded={expanded}
            counts={counts}
            onSelect={selectCategory}
            onToggle={toggleExpand}
          />
        </nav>
      </aside>

      <main className="min-w-0 flex-1">
        {query ? (
          <SearchResults query={query} search={searchQuery} />
        ) : (
          <>
            <div className="mb-6 flex items-center justify-between gap-4">
              <div className="min-w-0">
                {selectedCategory && <Breadcrumbs crumbs={categoryCrumbs} />}
              </div>
              <label className="flex shrink-0 items-center gap-2 text-sm text-gray-600">
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
                byPopularity={byPopularity}
              />
            ) : (
              <>
                {selectedCategory && (
                  <h1 className="mb-5 text-2xl font-bold text-gray-900">
                    {selectedCategory.name}
                  </h1>
                )}
                {categoryQuery.isLoading ? (
                  <p className="text-gray-500">Завантаження…</p>
                ) : (
                  <CategoryGrid products={sortedCategoryProducts} />
                )}
              </>
            )}
          </>
        )}
      </main>
    </div>
  )
}

function AllProductsView({
  products,
  categories,
  sortBy,
  byPopularity,
}: {
  products: ProductOut[]
  categories: CategoryOut[]
  sortBy: SortKey
  byPopularity: (a: ProductOut, b: ProductOut) => number
}) {
  // One slider per TOP-LEVEL (root) category, containing every product beneath
  // it — instead of a slider per leaf/brand category. A product's root is the
  // first entry of its category's ancestor path (or the category itself when it
  // is already a root).
  const roots = categories.filter((c) => c.parent_id == null)
  const rootIdOf = (p: ProductOut) => p.category.ancestors?.[0]?.id ?? p.category.id
  const sections = roots
    .map((root) => {
      const inRoot = products.filter((p) => rootIdOf(p) === root.id)
      return {
        category: root,
        items:
          sortBy === 'popular'
            ? [...inRoot].sort(byPopularity)
            : sortProducts(inRoot, sortBy),
      }
    })
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
                <ProductCard product={product} noZoom />
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
