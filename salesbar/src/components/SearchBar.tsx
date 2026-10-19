import { useState, type FormEvent } from 'react'
import { useShopStore } from '../store'

function SearchBar({ disabled }: { disabled: boolean }) {
  const query = useShopStore((state) => state.query)
  const setQuery = useShopStore((state) => state.setQuery)
  const [draft, setDraft] = useState(query)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setQuery(draft)
  }

  const clear = () => {
    setDraft('')
    setQuery('')
  }

  return (
    <form onSubmit={submit} role="search" className="flex w-full gap-2">
      <div className="relative min-w-0 flex-1">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask Salesbar: waterproof jacket in M, no wool, under $120"
          aria-label="Search products"
          disabled={disabled}
          className="w-full rounded-xl border-3 border-text bg-background py-3 pr-10 pl-4 text-base text-text shadow-[4px_4px_0_0_var(--color-brand)] placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2 disabled:bg-surface"
        />
        {draft !== '' && (
          <button
            type="button"
            onClick={clear}
            aria-label="Clear search"
            className="absolute top-1/2 right-3 -translate-y-1/2 cursor-pointer text-xl leading-none font-bold text-muted hover:text-text"
          >
            ×
          </button>
        )}
      </div>
      <button
        type="submit"
        disabled={disabled || draft.trim() === ''}
        className="cursor-pointer rounded-xl border-3 border-text bg-brand px-5 py-3 text-base font-extrabold text-white shadow-[4px_4px_0_0_var(--color-text)] hover:bg-brand/90 focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-border disabled:text-muted"
      >
        Search
      </button>
    </form>
  )
}

export default SearchBar
