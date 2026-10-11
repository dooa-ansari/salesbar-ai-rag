import { describe, expect, it } from 'vitest'
import {
  createGraphEdge,
  createGraphNode,
  defaultNodeData,
  humanizeGraph,
  layoutGraph,
  nodeEmbeddingTexts,
  toFlowEdge,
  toFlowNode,
  type GraphEdgeType,
  type GraphNodeType,
} from './graph'

function node(data: Partial<GraphNodeType['data']> = {}, overrides: Partial<GraphNodeType> = {}): GraphNodeType {
  return {
    id: overrides.id ?? 'n1',
    type: 'graph',
    position: { x: 0, y: 0 },
    data: { name: '', type: '', properties: [], ...data },
    ...overrides,
  }
}

describe('humanizeGraph / nodeEmbeddingTexts (shared describeNode logic)', () => {
  it('describes name, type (with the right article) and properties as sentences', () => {
    const text = humanizeGraph([
      node({
        name: 'Robert',
        type: 'Person',
        properties: [{ name: 'age', value: '72' }],
      }),
    ])
    expect(text).toBe("Robert is a person. Robert's age is 72.")
  })

  it('uses "an" before a vowel-leading type', () => {
    const text = humanizeGraph([node({ name: 'Nimbus', type: 'Entity' })])
    expect(text).toBe('Nimbus is an entity.')
  })

  it('appends the description as-is, adding a period only if missing', () => {
    const withPeriod = humanizeGraph([
      node({ name: 'X', type: 'Thing', description: 'Already punctuated.' }),
    ])
    expect(withPeriod).toContain('Already punctuated.')
    expect(withPeriod).not.toContain('Already punctuated..')

    const withoutPeriod = humanizeGraph([
      node({ name: 'X', type: 'Thing', description: 'No period' }),
    ])
    expect(withoutPeriod).toContain('No period.')
  })

  it('skips properties with a blank name or value', () => {
    const text = humanizeGraph([
      node({
        name: 'X',
        type: 'Thing',
        properties: [
          { name: '', value: 'should be skipped' },
          { name: 'should be skipped too', value: '' },
          { name: 'kept', value: 'yes' },
        ],
      }),
    ])
    expect(text).toContain("X's kept is yes.")
    expect(text).not.toContain('should be skipped')
  })

  it('treats a node with no name as having nothing to say', () => {
    expect(humanizeGraph([node({ name: '   ', type: 'Thing' })])).toBe('')
    expect(nodeEmbeddingTexts([node({ name: '', type: 'Thing' })])).toEqual([])
  })

  it('humanizeGraph joins multiple nodes and drops nameless ones', () => {
    const text = humanizeGraph([
      node({ name: 'A', type: 'Thing' }, { id: 'a' }),
      node({ name: '' }, { id: 'blank' }),
      node({ name: 'B', type: 'Thing' }, { id: 'b' }),
    ])
    expect(text).toBe('A is a thing. B is a thing.')
  })

  it('nodeEmbeddingTexts keeps each node\'s id paired with its own text, omitting empties', () => {
    const result = nodeEmbeddingTexts([
      node({ name: 'A', type: 'Thing' }, { id: 'a' }),
      node({ name: '' }, { id: 'blank' }),
      node({ name: 'B', type: 'Thing' }, { id: 'b' }),
    ])
    expect(result).toEqual([
      { id: 'a', text: 'A is a thing.' },
      { id: 'b', text: 'B is a thing.' },
    ])
  })

  it('never includes relationship/edge text (attributes only, by design)', () => {
    // There's no edges parameter at all — this just pins that down so a
    // future "helpfully" add one back without re-deciding the tradeoff
    // (see the hybrid-retrieval design: relationships are read live from
    // Neo4j at search time, not baked into the embedding).
    const text = humanizeGraph([node({ name: 'A', type: 'Thing' })])
    expect(text).not.toMatch(/relat/i)
  })
})

describe('node/edge builders', () => {
  it('createGraphNode generates a unique id and carries the position/data through', () => {
    const data = defaultNodeData(1)
    const a = createGraphNode({ x: 10, y: 20 }, data)
    const b = createGraphNode({ x: 10, y: 20 }, data)

    expect(a.type).toBe('graph')
    expect(a.position).toEqual({ x: 10, y: 20 })
    expect(a.data).toEqual(data)
    expect(a.id).not.toBe(b.id)
  })

  it('defaultNodeData numbers the placeholder name and starts with no properties', () => {
    expect(defaultNodeData(3)).toEqual({ name: 'Node 3', type: 'Entity', properties: [] })
  })

  it('createGraphEdge defaults to an empty relationship and passes handle ids through', () => {
    const edge = createGraphEdge('a', 'b', { sourceHandle: 'link' })
    expect(edge.source).toBe('a')
    expect(edge.target).toBe('b')
    expect(edge.sourceHandle).toBe('link')
    expect(edge.targetHandle).toBeUndefined()
    expect(edge.data?.relationship).toBe('')
  })

  it('toFlowEdge sets the arrow marker and relationship/bend data', () => {
    const edge = toFlowEdge({
      id: 'e1',
      source: 'a',
      target: 'b',
      relationship: 'Father',
      bend: { x: 5, y: 5 },
    })
    expect(edge.type).toBe('relationship')
    expect(edge.markerEnd).toMatchObject({ type: 'arrowclosed' })
    expect(edge.data).toEqual({ relationship: 'Father', bend: { x: 5, y: 5 } })
  })

  it('toFlowNode keeps the stored id/position/data and sets the React Flow type', () => {
    const data = defaultNodeData(1)
    const flowNode = toFlowNode({ id: 'n1', position: { x: 1, y: 2 }, data })
    expect(flowNode).toEqual({ id: 'n1', type: 'graph', position: { x: 1, y: 2 }, data })
  })
})

describe('layoutGraph', () => {
  // Builds a small but still-congested graph: a hub connected to many
  // leaves, each leaf also cross-linked to the next — enough that naive
  // fixed-spacing placement (what the overlap bug actually was) would
  // overlap, so this is a real regression test for that bug, not just a
  // smoke test.
  function congestedGraph(leafCount: number): { nodes: GraphNodeType[]; edges: GraphEdgeType[] } {
    const nodes: GraphNodeType[] = [node({ name: 'Hub', type: 'Thing' }, { id: 'hub' })]
    const edges: GraphEdgeType[] = []
    for (let i = 0; i < leafCount; i++) {
      const id = `leaf-${i}`
      nodes.push(node({ name: `Leaf ${i}`, type: 'Thing', properties: [{ name: 'p', value: 'v' }] }, { id }))
      edges.push(createGraphEdge('hub', id))
      if (i > 0) edges.push(createGraphEdge(`leaf-${i - 1}`, id))
    }
    return { nodes, edges }
  }

  function overlaps(
    a: { x: number; y: number },
    b: { x: number; y: number },
    width: number,
    height: number,
  ): boolean {
    return Math.abs(a.x - b.x) < width && Math.abs(a.y - b.y) < height
  }

  it('produces no overlapping node positions on a congested graph', () => {
    const { nodes, edges } = congestedGraph(20)
    const laidOut = layoutGraph(nodes, edges)

    for (let i = 0; i < laidOut.length; i++) {
      for (let j = i + 1; j < laidOut.length; j++) {
        // Fallback size used by layoutGraph for unmeasured nodes.
        expect(overlaps(laidOut[i].position, laidOut[j].position, 260, 220)).toBe(false)
      }
    }
  })

  it('only changes position — id and data are untouched', () => {
    const { nodes, edges } = congestedGraph(5)
    const laidOut = layoutGraph(nodes, edges)

    expect(laidOut.map((n) => n.id)).toEqual(nodes.map((n) => n.id))
    laidOut.forEach((laidOutNode, i) => {
      expect(laidOutNode.data).toBe(nodes[i].data)
    })
  })

  it('spreads out nodes with no edges at all instead of stacking them', () => {
    const nodes = [
      node({ name: 'A' }, { id: 'a' }),
      node({ name: 'B' }, { id: 'b' }),
      node({ name: 'C' }, { id: 'c' }),
    ]
    const laidOut = layoutGraph(nodes, [])
    const positions = laidOut.map((n) => `${n.position.x},${n.position.y}`)
    expect(new Set(positions).size).toBe(3)
  })
})
