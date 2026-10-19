import { useMemo } from 'react'
import type { ShopConstraint, ShopMatch } from '../api'
import { useProducts, useSearch } from '../hooks'
import type { Product } from '../product'
import { useShopStore, type SortOrder } from '../store'
import type { ChipKind } from './Chip'
import ProductGrid, { type GridItem } from './ProductGrid'
import RuledOut, { type RuledOutItem } from './RuledOut'
import Toolbar from './Toolbar'

const CONSTRAINT_STYLES: Record<ShopConstraint['kind'], string> = {
  required: 'bg-text text-white',
  safety: 'bg-chip-ruled-out text-chip-ruled-out-text',
  near: 'bg-chip-exact text-chip-exact-text',
  soft: 'bg-chip-exact text-chip-exact-text',
}

function chipFor(match: ShopMatch): ChipKind | undefined {
  return match.match === 'related' ? undefined : match.match
}

function sortItems<T extends { product: Product }>(items: T[], sort: SortOrder) {
  if (sort === 'featured') return items
  const direction = sort === 'price_asc' ? 1 : -1
  return [...items].sort(
    (a, b) => direction * ((a.product.price ?? Infinity) - (b.product.price ?? Infinity)),
  )
}

function Storefront({ catalogId }: { catalogId: string }) {
  const query = useShopStore((state) => state.query)
  const category = useShopStore((state) => state.category)
  const sort = useShopStore((state) => state.sort)
  const products = useProducts(catalogId)
  const search = useSearch(catalogId, query)
  const searching = query.trim() !== ''

  const categories = useMemo(
    () => [...new Set((products.data ?? []).map((product) => product.category))].sort(),
    [products.data],
  )

  const { items, ruledOut } = useMemo(() => {
    const all = products.data ?? []
    const byId = new Map<string, Product>(all.map((product) => [product.id, product]))
    const resolve = (matches: ShopMatch[]) =>
      matches.flatMap((match) => {
        const product = byId.get(match.productId)
        return product ? [{ product, chip: chipFor(match), reasons: match.reasons }] : []
      })
    const inCategory = <T extends { product: Product }>(list: T[]) =>
      category ? list.filter(({ product }) => product.category === category) : list

    const list: GridItem[] = searching ? resolve(search.data?.results ?? []) : all.map((product) => ({ product }))
    const left: RuledOutItem[] = searching ? resolve(search.data?.ruledOut ?? []) : []
    return { items: sortItems(inCategory(list), sort), ruledOut: inCategory(left) }
  }, [products.data, search.data, searching, category, sort])

  if (products.isLoading) return <p className="text-muted">Loading products…</p>
  if (products.error) return <p className="font-bold text-chip-ruled-out">{products.error.message}</p>

  return (
    <div className="flex flex-col gap-6">
      {searching && (
        <section className="flex flex-col gap-3 rounded-xl border-3 border-text bg-chip-alternative p-5 shadow-[6px_6px_0_0_var(--color-brand)]">
          <div className="text-xs font-extrabold tracking-widest text-brand uppercase">Salesbar says</div>
          {search.isFetching ? (
            <p className="font-medium text-text">Looking through the shelves for “{query}”…</p>
          ) : search.error ? (
            <p className="font-bold text-chip-ruled-out">{search.error.message}</p>
          ) : (
            search.data && (
              <>
                <p className="text-lg font-bold text-text">{search.data.message}</p>
                {search.data.constraints.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold text-muted">You asked for</span>
                    {search.data.constraints.map((constraint) => (
                      <span
                        key={constraint.label}
                        className={`rounded-full border-2 border-text px-2.5 py-0.5 text-xs font-extrabold ${CONSTRAINT_STYLES[constraint.kind]}`}
                      >
                        {constraint.label}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )
          )}
        </section>
      )}

      <Toolbar categories={categories} />

      {!(searching && search.isFetching) && (
        <>
          <div className="text-sm font-bold text-muted">
            {items.length} {items.length === 1 ? 'product' : 'products'}
            {searching && ` for “${query}”`}
          </div>
          {items.length > 0 ? (
            <ProductGrid items={items} />
          ) : (
            !searching && (
            <p className="rounded-xl border-3 border-dashed border-border p-8 text-center font-bold text-muted">
              Nothing on the shelves in this category.
            </p>
            )
          )}
          <RuledOut items={ruledOut} />
        </>
      )}
    </div>
  )
}

export default Storefront
