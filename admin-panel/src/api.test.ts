import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  generateEmbeddings,
  getGraph,
  listGraphs,
  saveGraph,
  saveGraphText,
  searchGraph,
} from './api'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api request/response handling', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns the parsed JSON body on success', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([{ id: 'g1', name: 'A', updatedAt: '', nodes: 0, edges: 0 }]))

    const result = await listGraphs()

    expect(result).toEqual([{ id: 'g1', name: 'A', updatedAt: '', nodes: 0, edges: 0 }])
  })

  it('surfaces a FastAPI JSON error body as the thrown message', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Graph name is required' }), { status: 422 }),
    )

    await expect(saveGraph('', { nodes: [], edges: [] })).rejects.toThrow(
      /Request failed \(422\).*Graph name is required/,
    )
  })

  it('falls back to the raw text when the error body is not JSON', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('<html>Bad Gateway</html>', { status: 502 }))

    await expect(listGraphs()).rejects.toThrow(/Request failed \(502\).*Bad Gateway/)
  })

  it('getGraph URL-encodes the graph id', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ id: 'a/b', name: 'X', nodes: [], edges: [] }))

    await getGraph('a/b c')

    expect(fetch).toHaveBeenCalledWith('/api/graphs/a%2Fb%20c', expect.anything())
  })

  it('saveGraph POSTs the name merged with the graph payload', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ message: 'ok', status: 'success', id: 'g1', name: 'My Graph', nodes: 0, edges: 0 }),
    )

    await saveGraph('My Graph', { nodes: [], edges: [] })

    expect(fetch).toHaveBeenCalledWith('/api/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'My Graph', nodes: [], edges: [] }),
    })
  })

  it('saveGraphText PUTs just the text', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ status: 'success', message: 'Text saved' }))

    await saveGraphText('g1', 'hello')

    expect(fetch).toHaveBeenCalledWith('/api/graphs/g1/text', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'hello' }),
    })
  })

  it('generateEmbeddings POSTs the node list under "nodes"', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ status: 'success', message: 'ok', count: 1, dimensions: 1024 }),
    )

    await generateEmbeddings('g1', [{ id: 'n1', text: 'A is a thing.' }])

    expect(fetch).toHaveBeenCalledWith('/api/graphs/g1/embeddings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nodes: [{ id: 'n1', text: 'A is a thing.' }] }),
    })
  })

  it('searchGraph POSTs the query', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ query: 'q', results: [], answer: null }))

    await searchGraph('g1', 'who is the father?')

    expect(fetch).toHaveBeenCalledWith('/api/graphs/g1/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'who is the father?' }),
    })
  })

  it('a bodyless GET sends no Content-Type header', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([]))

    await listGraphs()

    const [, init] = vi.mocked(fetch).mock.calls[0]
    expect(init?.headers).toBeUndefined()
  })
})
