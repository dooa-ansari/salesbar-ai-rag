import SearchBar from './components/SearchBar'
import Storefront from './components/Storefront'
import { CATALOG_NAME, useCatalog } from './hooks'

function App() {
  const catalog = useCatalog()
  const catalogId = catalog.data?.id

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b-3 border-text bg-surface">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:gap-8">
          <a href="/" className="shrink-0 text-3xl font-black tracking-tight text-brand italic [text-shadow:3px_3px_0_var(--color-chip-exact)]">
            Salesbar
          </a>
          <SearchBar disabled={!catalogId} />
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl px-4 py-8">
        {catalog.isLoading && <p className="text-muted">Connecting…</p>}
        {catalog.error && <p className="font-bold text-chip-ruled-out">{catalog.error.message}</p>}
        {catalog.data === null && (
          <p className="font-bold text-chip-ruled-out">Catalog "{CATALOG_NAME}" was not found on the backend.</p>
        )}
        {catalogId && <Storefront catalogId={catalogId} />}
      </main>
    </div>
  )
}

export default App
