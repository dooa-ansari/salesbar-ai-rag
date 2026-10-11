import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ReactFlow,
  Background,
  Controls,
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import Button from '../components/Button'
import GraphNode from '../components/GraphNode'
import RelationshipEdge from '../components/RelationshipEdge'
import SearchPanel from '../components/SearchPanel'
import {
  generateEmbeddings,
  getGraph,
  saveGraph as apiSaveGraph,
  saveGraphText,
  type GraphExport,
  type SearchResultNode,
} from '../api'
import { HighlightContext, type HighlightContextValue } from '../HighlightContext'
import { LinkContext, type LinkContextValue, type LinkDirection } from '../LinkContext'
import {
  IN_BOTTOM_HANDLE_ID,
  LINK_HANDLE_ID,
  LINK_UP_HANDLE_ID,
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
} from '../graph'

// Defined outside the component so React Flow doesn't see new objects every render.
const nodeTypes = { graph: GraphNode }
const edgeTypes = { relationship: RelationshipEdge }

const AUTOSAVE_SECONDS = 15

// Order-independent fingerprint of what "Generate embeddings" would currently
// send, so edits (including deleting a node) can be told apart from a no-op.
function embeddingSignature(nodes: GraphNodeType[]): string {
  return nodeEmbeddingTexts(nodes)
    .map((target) => `${target.id}::${target.text}`)
    .sort()
    .join('|')
}

// Pans/zooms to frame a search's highlighted nodes. Rendered inside <ReactFlow>
// since useReactFlow only works in its descendants.
function FitViewToHighlight({ nodeIds }: { nodeIds: string[] }) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    if (nodeIds.length === 0) return
    fitView({ nodes: nodeIds.map((nodeId) => ({ id: nodeId })), padding: 0.3, duration: 400 })
  }, [nodeIds, fitView])
  return null
}

// Reframes the canvas after "Auto-arrange" moves every node. `version` just
// needs to change — the new positions are already in the store by then.
function FitViewOnLayout({ version }: { version: number }) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    if (version === 0) return
    fitView({ padding: 0.2, duration: 400 })
  }, [version, fitView])
  return null
}

function GraphEditorPage() {
  // Route is /graphs/new for a blank canvas, or /graphs/:id for a saved one.
  const { id } = useParams<{ id: string }>()
  const isNew = id === 'new'
  const navigate = useNavigate()

  const [nodes, setNodes, onNodesChange] = useNodesState<GraphNodeType>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<GraphEdgeType>([])
  const [graphName, setGraphName] = useState('')

  // Autosave ------------------------------------------------------------------
  // Compares actual content, not array identity — React Flow replaces the
  // nodes/edges arrays for non-edits too (measuring, selecting), which would
  // otherwise misfire as a change.
  const snapshotContent = useCallback(
    (
      snapNodes: GraphNodeType[],
      snapEdges: GraphEdgeType[],
      snapName: string,
    ): string =>
      JSON.stringify({
        name: snapName,
        nodes: snapNodes.map(({ id: nodeId, position, data }) => ({
          id: nodeId,
          position,
          data,
        })),
        edges: snapEdges.map(
          ({ id: edgeId, source, target, sourceHandle, targetHandle, data }) => ({
            id: edgeId,
            source,
            target,
            sourceHandle,
            targetHandle,
            data,
          }),
        ),
      }),
    [],
  )

  // Content as of the last load/save — dirty means "differs from this."
  const baselineSnapshotRef = useRef('')
  // Content as of the last check — lets a second edit be told apart from "no
  // real change," so it still resets the countdown.
  const lastSeenSnapshotRef = useRef('')
  const [dirty, setDirty] = useState(false)
  const [changeVersion, setChangeVersion] = useState(0)

  // What "Generate embeddings" last actually sent (or, on load, what the
  // loaded nodes imply was sent) — compared against the live graph to flag
  // embeddings that no longer match, e.g. after a node is edited or deleted.
  const embeddingBaselineRef = useRef<string | null>(null)

  // Loading an existing graph -------------------------------------------------

  const [loadState, setLoadState] = useState<
    { status: 'loading' } | { status: 'error'; message: string } | null
  >(isNew ? null : { status: 'loading' })

  useEffect(() => {
    if (isNew || !id) {
      setNodes([])
      setEdges([])
      setGraphName('')
      setGeneratedText(null)
      setEmbeddedNodeCount(null)
      embeddingBaselineRef.current = null
      setLoadState(null)
      setMatchedNodeIds(new Set())
      setNeighborNodeIds(new Set())
      setHighlightedEdgeIds(new Set())
      baselineSnapshotRef.current = lastSeenSnapshotRef.current = snapshotContent(
        [],
        [],
        '',
      )
      setDirty(false)
      return
    }

    let cancelled = false
    setLoadState({ status: 'loading' })
    getGraph(id)
      .then((graph) => {
        if (cancelled) return
        const loadedEdges = graph.edges.map(toFlowEdge)
        // Re-lay out on every load so nodes never open overlapping.
        const loadedNodes = layoutGraph(graph.nodes.map(toFlowNode), loadedEdges)
        setNodes(loadedNodes)
        setEdges(loadedEdges)
        setGraphName(graph.name)
        setGeneratedText(graph.text ?? null)
        const embeddedNodes = graph.nodes.filter((node) => node.embeddingDimensions)
        setEmbeddedNodeCount(embeddedNodes.length)
        setEmbeddingDimensions(embeddedNodes[0]?.embeddingDimensions ?? null)
        // Assumes the stored embeddings matched the loaded nodes at load time —
        // true unless the graph was edited directly outside this editor.
        embeddingBaselineRef.current = embeddedNodes.length > 0 ? embeddingSignature(loadedNodes) : null
        setLoadState(null)
        setMatchedNodeIds(new Set())
        setNeighborNodeIds(new Set())
        setHighlightedEdgeIds(new Set())
        baselineSnapshotRef.current = lastSeenSnapshotRef.current = snapshotContent(
          loadedNodes,
          loadedEdges,
          graph.name,
        )
        setDirty(false)
        setLayoutVersion((version) => version + 1)
      })
      .catch((error) => {
        if (cancelled) return
        setLoadState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Failed to load graph',
        })
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- setNodes/setEdges/snapshotContent are stable
  }, [id, isNew])

  useEffect(() => {
    const current = snapshotContent(nodes, edges, graphName)
    if (current === lastSeenSnapshotRef.current) return // no real change, e.g. just a node being selected
    lastSeenSnapshotRef.current = current

    if (current === baselineSnapshotRef.current) {
      setDirty(false)
      return
    }
    setDirty(true)
    // Bumped on every edit, even while already dirty, to restart the countdown.
    setChangeVersion((version) => version + 1)
  }, [nodes, edges, graphName, snapshotContent])

  // Every link gets its own edge, so already-connected nodes can link again.
  const linkNodes = useCallback(
    (sourceId: string, targetId: string, direction: LinkDirection) => {
      setEdges((current) => [
        ...current,
        createGraphEdge(
          sourceId,
          targetId,
          direction === 'up'
            ? { sourceHandle: LINK_UP_HANDLE_ID, targetHandle: IN_BOTTOM_HANDLE_ID }
            : { sourceHandle: LINK_HANDLE_ID },
        ),
      ])
    },
    [setEdges],
  )

  // Dragging from a node's top button makes a reverse link, from the bottom one a normal link.
  const onConnect = useCallback(
    (connection: Connection) =>
      linkNodes(
        connection.source,
        connection.target,
        connection.sourceHandle === LINK_UP_HANDLE_ID ? 'up' : 'down',
      ),
    [linkNodes],
  )

  const isValidConnection = useCallback(
    (connection: Connection | GraphEdgeType) =>
      connection.source !== connection.target,
    [],
  )

  // Click-to-connect: click a node's "+" (or "↑"), then click the node to link to.
  const [linking, setLinking] = useState<LinkContextValue['linking']>(null)

  const linkContext = useMemo<LinkContextValue>(
    () => ({
      linking,
      toggleLink: (nodeId, direction) =>
        setLinking((current) =>
          current?.nodeId === nodeId && current.direction === direction
            ? null
            : { nodeId, direction },
        ),
    }),
    [linking],
  )

  const onNodeClick = useCallback(
    (_: unknown, node: GraphNodeType) => {
      if (!linking || node.id === linking.nodeId) return
      linkNodes(linking.nodeId, node.id, linking.direction)
      setLinking(null)
    },
    [linking, linkNodes],
  )

  useEffect(() => {
    if (!linking) return
    const cancel = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLinking(null)
    }
    window.addEventListener('keydown', cancel)
    return () => window.removeEventListener('keydown', cancel)
  }, [linking])

  const addNode = useCallback(() => {
    setNodes((current) => [
      ...current,
      createGraphNode(
        { x: Math.random() * 400, y: Math.random() * 300 },
        defaultNodeData(current.length + 1),
      ),
    ])
  }, [setNodes])

  // Auto-arrange: re-lays out every node (dagre) so nothing overlaps.
  const [layoutVersion, setLayoutVersion] = useState(0)
  const autoArrange = useCallback(() => {
    setNodes((current) => layoutGraph(current, edges))
    setLayoutVersion((version) => version + 1)
  }, [edges, setNodes])

  // Saving ------------------------------------------------------------------

  const [saveState, setSaveState] = useState<
    { status: 'saving' } | { status: 'success' | 'error'; message: string } | null
  >(null)

  const saveGraph = useCallback(async () => {
    const name = graphName.trim()
    if (!name) return

    const graph: GraphExport = {
      nodes: nodes.map(({ id, type, position, data }) => ({
        id,
        type,
        position,
        data,
      })),
      edges: edges.map(({ id, source, target, sourceHandle, targetHandle, data }) => ({
        id,
        source,
        target,
        sourceHandle,
        targetHandle,
        relationship: data?.relationship ?? '',
        bend: data?.bend,
      })),
    }

    setSaveState({ status: 'saving' })
    try {
      const result = await apiSaveGraph(name, graph)
      setSaveState({
        status: 'success',
        message: `Saved "${result.name}" (${result.nodes} node${result.nodes === 1 ? '' : 's'}, ${result.edges} edge${result.edges === 1 ? '' : 's'})`,
      })
      // Re-baseline against what was just saved, not stale pre-save content.
      baselineSnapshotRef.current = lastSeenSnapshotRef.current = snapshotContent(
        nodes,
        edges,
        name,
      )
      setDirty(false)
      // A brand-new graph now has a real id — move the URL onto it.
      if (isNew) navigate(`/graphs/${result.id}`, { replace: true })
    } catch (error) {
      setSaveState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Save failed',
      })
    }
  }, [graphName, nodes, edges, isNew, navigate, snapshotContent])

  // Autosaves AUTOSAVE_SECONDS after the graph goes dirty, resetting on each edit.
  const [autosaveCountdown, setAutosaveCountdown] = useState<number | null>(null)

  useEffect(() => {
    if (!dirty || !graphName.trim() || saveState?.status === 'saving') {
      setAutosaveCountdown(null)
      return
    }
    setAutosaveCountdown(AUTOSAVE_SECONDS)
    const interval = setInterval(() => {
      setAutosaveCountdown((current) =>
        current !== null && current > 0 ? current - 1 : current,
      )
    }, 1000)
    return () => clearInterval(interval)
    // changeVersion restarts the countdown on each edit; `dirty` alone can't.
  }, [dirty, changeVersion, graphName, saveState?.status])

  useEffect(() => {
    if (autosaveCountdown === 0) saveGraph()
  }, [autosaveCountdown, saveGraph])

  // The status message clears itself so it doesn't linger forever.
  useEffect(() => {
    if (!saveState || saveState.status === 'saving') return
    const timer = setTimeout(() => setSaveState(null), 4000)
    return () => clearTimeout(timer)
  }, [saveState])

  // Generating text for embeddings ---------------------------------------

  const [generatedText, setGeneratedText] = useState<string | null>(null)
  const [textState, setTextState] = useState<
    { status: 'generating' } | { status: 'success' | 'error'; message: string } | null
  >(null)
  const [textModalOpen, setTextModalOpen] = useState(false)

  const generateText = useCallback(async () => {
    if (!id || isNew) return
    const text = humanizeGraph(nodes)

    setTextState({ status: 'generating' })
    try {
      await saveGraphText(id, text)
      setGeneratedText(text)
      setTextState({ status: 'success', message: 'Text generated and saved' })
    } catch (error) {
      setTextState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to generate text',
      })
    }
  }, [id, isNew, nodes])

  useEffect(() => {
    if (!textState || textState.status === 'generating') return
    const timer = setTimeout(() => setTextState(null), 4000)
    return () => clearTimeout(timer)
  }, [textState])

  // Generating embeddings ------------------------------------------------
  // One vector per node, via a single batched OpenRouter call.

  const [embeddedNodeCount, setEmbeddedNodeCount] = useState<number | null>(null)
  const [embeddingDimensions, setEmbeddingDimensions] = useState<number | null>(null)
  const [embeddingState, setEmbeddingState] = useState<
    { status: 'generating' } | { status: 'success' | 'error'; message: string } | null
  >(null)

  const generateEmbeddingsForGraph = useCallback(async () => {
    if (!id || isNew) return
    const targets = nodeEmbeddingTexts(nodes)
    if (targets.length === 0) {
      setEmbeddingState({ status: 'error', message: 'No named nodes to embed' })
      return
    }

    setEmbeddingState({ status: 'generating' })
    try {
      const result = await generateEmbeddings(id, targets)
      setEmbeddedNodeCount(result.count)
      setEmbeddingDimensions(result.dimensions)
      embeddingBaselineRef.current = targets.map((target) => `${target.id}::${target.text}`).sort().join('|')
      setEmbeddingState({
        status: 'success',
        message: `Generated embeddings for ${result.count} node${result.count === 1 ? '' : 's'} (${result.dimensions} dimensions each)`,
      })
    } catch (error) {
      setEmbeddingState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to generate embeddings',
      })
    }
  }, [id, isNew, nodes])

  useEffect(() => {
    if (!embeddingState || embeddingState.status === 'generating') return
    const timer = setTimeout(() => setEmbeddingState(null), 4000)
    return () => clearTimeout(timer)
  }, [embeddingState])

  // Search panel --------------------------------------------------------

  const [searchOpen, setSearchOpen] = useState(false)

  // Highlighting the traversal: matched nodes (vector search), the neighbors
  // pulled in only via the live Neo4j traversal from them, and the edges
  // actually walked between them.
  const [matchedNodeIds, setMatchedNodeIds] = useState<Set<string>>(new Set())
  const [neighborNodeIds, setNeighborNodeIds] = useState<Set<string>>(new Set())
  const [highlightedEdgeIds, setHighlightedEdgeIds] = useState<Set<string>>(new Set())

  const highlightContext = useMemo<HighlightContextValue>(
    () => ({ matchedNodeIds, neighborNodeIds, highlightedEdgeIds }),
    [matchedNodeIds, neighborNodeIds, highlightedEdgeIds],
  )
  const highlightedIds = useMemo(
    () => [...matchedNodeIds, ...neighborNodeIds],
    [matchedNodeIds, neighborNodeIds],
  )

  const clearHighlight = useCallback(() => {
    setMatchedNodeIds(new Set())
    setNeighborNodeIds(new Set())
    setHighlightedEdgeIds(new Set())
  }, [])

  const handleSearchResult = useCallback(
    (results: SearchResultNode[]) => {
      const matched = new Set(results.map((result) => result.id))
      const neighbors = new Set<string>()
      // Edges are matched by (source, target, relationship) since a node pair
      // can have several edges with different relationship labels.
      const edgeKeys = new Set<string>()
      for (const result of results) {
        for (const rel of result.relationships) {
          if (!matched.has(rel.otherId)) neighbors.add(rel.otherId)
          const [source, target] =
            rel.direction === 'outgoing'
              ? [result.id, rel.otherId]
              : [rel.otherId, result.id]
          edgeKeys.add(`${source}|${target}|${rel.relationship}`)
        }
      }
      setMatchedNodeIds(matched)
      setNeighborNodeIds(neighbors)
      setHighlightedEdgeIds(
        new Set(
          edges
            .filter((edge) =>
              edgeKeys.has(`${edge.source}|${edge.target}|${edge.data?.relationship ?? ''}`),
            )
            .map((edge) => edge.id),
        ),
      )
    },
    [edges],
  )

  // Whether the graph has changed (edited or deleted nodes) since the text/
  // embeddings used for search were last generated — including a load whose
  // stored text/embeddings no longer match the current nodes.
  const textStale = generatedText !== null && humanizeGraph(nodes) !== generatedText
  const embeddingsStale =
    embeddedNodeCount !== null && embeddingSignature(nodes) !== (embeddingBaselineRef.current ?? '')

  if (loadState?.status === 'loading') {
    return (
      <div className="flex h-full w-full items-center justify-center text-gray-500">
        Loading graph…
      </div>
    )
  }

  if (loadState?.status === 'error') {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-center">
        <p className="text-red-600">{loadState.message}</p>
        <Link to="/" className="text-primary-600 underline">
          Back to all graphs
        </Link>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <LinkContext.Provider value={linkContext}>
        <HighlightContext.Provider value={highlightContext}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onNodeClick={onNodeClick}
            onPaneClick={() => setLinking(null)}
          >
            <Panel position="top-left" className="flex flex-col items-start gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to="/"
                  className="inline-flex items-center rounded-md px-3 py-2 text-sm font-medium text-primary-700 hover:bg-primary-50"
                >
                  ← All graphs
                </Link>
                {/* Only needed for a graph's first node — the rest use the node's own "+". */}
                {nodes.length === 0 && <Button onClick={addNode}>Add node</Button>}

                {nodes.length > 1 && (
                  <Button variant="outline" onClick={autoArrange} title="Re-space nodes so they don't overlap">
                    Auto-arrange
                  </Button>
                )}

                <input
                  value={graphName}
                  onChange={(e) => setGraphName(e.target.value)}
                  placeholder="Graph name"
                  aria-label="Graph name"
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none"
                />
                <Button
                  variant="secondary"
                  onClick={saveGraph}
                  disabled={saveState?.status === 'saving' || !graphName.trim()}
                  // Keeps a stable accessible name even while the visible
                  // label cycles through the autosave countdown.
                  aria-label="Save graph"
                >
                  {saveState?.status === 'saving'
                    ? 'Saving…'
                    : autosaveCountdown !== null
                      ? `Autosaving in ${autosaveCountdown}s…`
                      : 'Save graph'}
                </Button>
  
                {saveState && saveState.status !== 'saving' && (
                  <span
                    className={`rounded-md px-3 py-2 text-sm ${
                      saveState.status === 'success'
                        ? 'bg-secondary-100 text-secondary-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {saveState.message}
                  </span>
                )}
              </div>
  
              {linking && (
                <span className="rounded-md bg-primary-100 px-3 py-2 text-sm text-primary-700">
                  {linking.direction === 'up'
                    ? 'Click the node this one points back to'
                    : 'Click the node to connect to'}{' '}
                  (Esc to cancel)
                </span>
              )}
            </Panel>
  
            {/* Search pipeline: text → embeddings → search. */}
            {!isNew && (
              <Panel position="bottom-center" className="mb-4 flex flex-col items-center gap-2">
                {(textStale || embeddingsStale) && (
                  <p className="rounded-md bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800">
                    The graph changed since{' '}
                    {textStale && embeddingsStale
                      ? 'the text and embeddings were'
                      : textStale
                        ? 'the text was'
                        : 'the embeddings were'}{' '}
                    generated — regenerate {textStale && embeddingsStale ? 'both' : textStale ? 'text' : 'embeddings'} for accurate search results.
                  </p>
                )}
                <div className="flex flex-wrap items-center justify-center gap-2 rounded-lg border border-primary-200 bg-white px-3 py-2 shadow-lg">
                  <span className="text-xs font-semibold tracking-wide text-gray-400 uppercase">
                    Prepare for search
                  </span>
  
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={generateText}
                      disabled={nodes.length === 0 || textState?.status === 'generating'}
                    >
                      {textState?.status === 'generating'
                        ? 'Generating…'
                        : generatedText
                          ? 'Regenerate text'
                          : 'Generate text'}
                    </Button>
                    {/* Only once there's something to view — not just disabled. */}
                    {generatedText && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setTextModalOpen(true)}
                      >
                        View text
                      </Button>
                    )}
                  </div>
  
                  <span className="text-gray-300">→</span>
  
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={generateEmbeddingsForGraph}
                      disabled={
                        nodes.length === 0 || embeddingState?.status === 'generating'
                      }
                    >
                      {embeddingState?.status === 'generating'
                        ? 'Generating…'
                        : embeddedNodeCount
                          ? 'Regenerate embeddings'
                          : 'Generate embeddings'}
                    </Button>
                    {/* Hidden while a fresh success message already says the same thing. */}
                    {!!embeddedNodeCount && embeddingState?.status !== 'success' && (
                      <span
                        className="rounded-full bg-secondary-100 px-2 py-0.5 text-xs font-medium text-secondary-700"
                        title={
                          embeddingDimensions
                            ? `${embeddingDimensions} dimensions each`
                            : undefined
                        }
                      >
                        {embeddedNodeCount} embedded
                      </span>
                    )}
                  </div>
  
                  <span className="text-gray-300">→</span>
  
                  <Button variant="secondary" onClick={() => setSearchOpen(true)}>
                    Search
                  </Button>
  
                  {textState && textState.status !== 'generating' && (
                    <span
                      className={`rounded-md px-3 py-2 text-sm ${
                        textState.status === 'success'
                          ? 'bg-secondary-100 text-secondary-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {textState.message}
                    </span>
                  )}
                  {embeddingState && embeddingState.status !== 'generating' && (
                    <span
                      className={`rounded-md px-3 py-2 text-sm ${
                        embeddingState.status === 'success'
                          ? 'bg-secondary-100 text-secondary-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {embeddingState.message}
                    </span>
                  )}
                </div>
              </Panel>
            )}
            <FitViewToHighlight nodeIds={highlightedIds} />
            <FitViewOnLayout version={layoutVersion} />
            <Background />
            <Controls />
          </ReactFlow>
        </HighlightContext.Provider>
      </LinkContext.Provider>

      {textModalOpen && generatedText && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setTextModalOpen(false)}
        >
          <div
            className="flex max-h-[80vh] w-full max-w-xl flex-col rounded-lg bg-white p-5 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between gap-4">
              <h2 className="text-lg font-semibold text-gray-900">Generated text</h2>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigator.clipboard.writeText(generatedText)}
                >
                  Copy
                </Button>
                <button
                  type="button"
                  aria-label="Close"
                  onClick={() => setTextModalOpen(false)}
                  className="cursor-pointer text-xl leading-none text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>
            </div>
            <p className="overflow-auto whitespace-pre-wrap text-sm text-gray-700">
              {generatedText}
            </p>
          </div>
        </div>
      )}

      {!isNew && id && (
        <SearchPanel
          graphId={id}
          open={searchOpen}
          onClose={() => {
            setSearchOpen(false)
            clearHighlight()
          }}
          onResult={handleSearchResult}
        />
      )}
    </div>
  )
}

export default GraphEditorPage
