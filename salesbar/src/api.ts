const API_BASE = '/api'

export type PropertyType = 'string' | 'integer' | 'float'

export type NodeProperty = {
  name: string
  type?: PropertyType
  value: string | number
}

export type ProductAttribute = {
  key?: string | null
  relationship: string
  name: string
  properties: NodeProperty[]
}

export type ProductSummary = {
  id: string
  catalogId?: string | null
  name: string
  description?: string | null
  properties: NodeProperty[]
  attributes: ProductAttribute[]
}

export type ShopConstraint = {
  label: string
  kind: 'required' | 'safety' | 'near' | 'soft'
}

export type MatchKind = 'exact' | 'near' | 'alternative' | 'related' | 'ruled-out'

export type ShopMatch = {
  productId: string
  match: MatchKind
  reasons: string[]
  score: number
}

export type ShopSearchResponse = {
  query: string
  constraints: ShopConstraint[]
  message: string
  results: ShopMatch[]
  ruledOut: ShopMatch[]
}

export type SavedGraphSummary = {
  id: string
  name: string
  updatedAt: string
  nodes: number
  edges: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })

  if (!response.ok) {
    const body = await response.text()
    let detail = body
    try {
      detail = JSON.stringify(JSON.parse(body).detail)
    } catch {
      detail = body
    }
    throw new Error(`Request failed (${response.status}): ${detail}`)
  }

  return response.json()
}

export function listGraphs(): Promise<SavedGraphSummary[]> {
  return request('/graphs')
}

export function listProducts(graphId: string): Promise<ProductSummary[]> {
  return request(`/graphs/${encodeURIComponent(graphId)}/products`)
}

export function shopSearch(graphId: string, query: string): Promise<ShopSearchResponse> {
  return request(`/graphs/${encodeURIComponent(graphId)}/shop-search`, {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}
