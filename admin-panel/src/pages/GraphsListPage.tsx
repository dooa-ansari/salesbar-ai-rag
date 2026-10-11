import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { buttonClassName } from '../components/buttonStyles'
import { listGraphs, type SavedGraphSummary } from '../api'

type State =
  | { status: 'loading' }
  | { status: 'loaded'; graphs: SavedGraphSummary[] }
  | { status: 'error'; message: string }

function GraphsListPage() {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    listGraphs()
      .then((graphs) => {
        if (!cancelled) setState({ status: 'loaded', graphs })
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Failed to load graphs',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="mx-auto h-full w-full max-w-3xl overflow-auto px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Saved graphs</h1>
        <Link to="/graphs/new" className={buttonClassName('primary', 'md')}>
          + New graph
        </Link>
      </div>

      {state.status === 'loading' && <p className="text-gray-500">Loading…</p>}

      {state.status === 'error' && (
        <p className="rounded-md bg-red-100 px-4 py-3 text-red-700">{state.message}</p>
      )}

      {state.status === 'loaded' &&
        (state.graphs.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 px-6 py-12 text-center text-gray-500">
            No saved graphs yet.{' '}
            <Link to="/graphs/new" className="text-primary-600 underline">
              Create one
            </Link>
            .
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {state.graphs.map((graph) => (
              <li key={graph.id}>
                <Link
                  to={`/graphs/${graph.id}`}
                  className="block rounded-lg border border-gray-200 bg-white px-5 py-4 shadow-sm transition-colors hover:border-primary-300 hover:bg-primary-50"
                >
                  <div className="font-medium text-gray-900">{graph.name}</div>
                  <div className="mt-1 text-sm text-gray-500">
                    {graph.nodes} node{graph.nodes === 1 ? '' : 's'}, {graph.edges} edge
                    {graph.edges === 1 ? '' : 's'} · updated{' '}
                    {new Date(graph.updatedAt).toLocaleString()}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </div>
  )
}

export default GraphsListPage
