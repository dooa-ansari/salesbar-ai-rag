import { useEffect, useRef, useState, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { searchGraph, type SearchResultNode } from '../api'

type HistoryEntry =
  | { kind: 'query'; text: string }
  | { kind: 'results'; query: string; results: SearchResultNode[]; answer?: string | null }
  | { kind: 'error'; message: string }

function ResultCard({ result }: { result: SearchResultNode }) {
  return (
    <div className="rounded-md border border-primary-200 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-primary-700">{result.name}</span>
        <span className="shrink-0 rounded-full bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700">
          {Math.round(result.score * 100)}% match
        </span>
      </div>
      <div className="mt-0.5 text-xs text-gray-500">{result.type}</div>
      {result.description && (
        <p className="mt-1 text-xs text-gray-600">{result.description}</p>
      )}
      {result.properties.length > 0 && (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 border-t border-secondary-100 pt-1.5 text-xs">
          {result.properties.map((property, index) => (
            <div key={index} className="contents">
              <dt className="font-medium text-secondary-700">{property.name}</dt>
              <dd className="break-words text-gray-700">{property.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {result.relationships.length > 0 && (
        <div className="mt-2 border-t border-primary-100 pt-1.5 text-xs text-gray-700">
          {result.relationships.map((rel, index) => (
            <div key={index}>
              {rel.direction === 'outgoing'
                ? `→ ${rel.relationship} → ${rel.otherName}`
                : `← ${rel.relationship} ← ${rel.otherName}`}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SearchPanel({
  graphId,
  open,
  onClose,
  onResult,
}: {
  graphId: string
  open: boolean
  onClose: () => void
  // Reports each search's results up, so the canvas can highlight them.
  onResult?: (results: SearchResultNode[]) => void
}) {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [history])

  useEffect(() => {
    if (!open) return
    const cancel = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', cancel)
    return () => window.removeEventListener('keydown', cancel)
  }, [open, onClose])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const text = query.trim()
    if (!text || searching) return

    setHistory((current) => [...current, { kind: 'query', text }])
    setQuery('')
    setSearching(true)
    try {
      const response = await searchGraph(graphId, text)
      setHistory((current) => [
        ...current,
        {
          kind: 'results',
          query: text,
          results: response.results,
          answer: response.answer,
        },
      ])
      onResult?.(response.results)
    } catch (error) {
      setHistory((current) => [
        ...current,
        {
          kind: 'error',
          message: error instanceof Error ? error.message : 'Search failed',
        },
      ])
    } finally {
      setSearching(false)
    }
  }

  // A real portal, rendered onto <body>, outside React Flow's own DOM subtree.
  return createPortal(
    <div
      aria-hidden={!open}
      className={`fixed inset-y-0 right-0 z-50 flex w-96 max-w-full flex-col border-l border-gray-200 bg-white shadow-xl transition-transform duration-200 ${
        open ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h2 className="text-base font-semibold text-gray-900">Search this graph</h2>
        <button
          type="button"
          aria-label="Close search panel"
          onClick={onClose}
          className="cursor-pointer text-xl leading-none text-gray-400 hover:text-gray-600"
        >
          ×
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto px-4 py-3">
        {history.length === 0 && (
          <p className="text-sm text-gray-500">
            Ask a question about this graph — it's matched against each node's
            embedding (run "Generate embeddings" first if you haven't).
          </p>
        )}
        <div className="flex flex-col gap-3">
          {history.map((entry, index) => {
            if (entry.kind === 'query') {
              return (
                <div key={index} className="ml-auto max-w-[85%] rounded-lg bg-primary-600 px-3 py-2 text-sm text-white">
                  {entry.text}
                </div>
              )
            }
            if (entry.kind === 'error') {
              return (
                <div
                  key={index}
                  className="rounded-md bg-red-100 px-3 py-2 text-sm text-red-700"
                >
                  {entry.message}
                </div>
              )
            }
            return (
              <div key={index} className="flex flex-col gap-2">
                {entry.answer && (
                  <div className="mr-auto max-w-[90%] rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-800">
                    {entry.answer}
                  </div>
                )}
                {entry.results.length === 0 ? (
                  <p className="text-sm text-gray-500">No matching nodes found.</p>
                ) : (
                  <>
                    <div className="mt-1 text-xs font-medium text-gray-400 uppercase">
                      Matched nodes
                    </div>
                    {entry.results.map((result) => (
                      <ResultCard key={result.id} result={result} />
                    ))}
                  </>
                )}
              </div>
            )
          })}
          {searching && <p className="text-sm text-gray-500">Searching…</p>}
        </div>
      </div>

      <form onSubmit={submit} className="flex items-center gap-2 border-t border-gray-200 p-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question…"
          aria-label="Search query"
          disabled={searching}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={searching || !query.trim()}
          className="cursor-pointer rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>,
    document.body,
  )
}

export default SearchPanel
