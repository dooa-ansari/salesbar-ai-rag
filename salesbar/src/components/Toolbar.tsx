import { useShopStore, type SortOrder } from '../store'

function Toolbar({ categories }: { categories: string[] }) {
  const category = useShopStore((state) => state.category)
  const sort = useShopStore((state) => state.sort)
  const setCategory = useShopStore((state) => state.setCategory)
  const setSort = useShopStore((state) => state.setSort)

  const tab = (value: string | null, label: string) => (
    <button
      key={label}
      type="button"
      onClick={() => setCategory(value)}
      aria-pressed={category === value}
      className={`cursor-pointer rounded-full border-2 border-text px-4 py-1.5 text-sm font-extrabold ${
        category === value ? 'bg-text text-white' : 'bg-background text-text hover:bg-surface'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-2">
        {tab(null, 'All')}
        {categories.map((name) => tab(name, name))}
      </div>
      <label className="flex items-center gap-2 text-sm font-bold text-text">
        Sort
        <select
          value={sort}
          onChange={(event) => setSort(event.target.value as SortOrder)}
          className="cursor-pointer rounded-lg border-2 border-text bg-background px-2 py-1.5 text-sm font-bold text-text"
        >
          <option value="featured">Featured</option>
          <option value="price_asc">Price: low to high</option>
          <option value="price_desc">Price: high to low</option>
        </select>
      </label>
    </div>
  )
}

export default Toolbar
