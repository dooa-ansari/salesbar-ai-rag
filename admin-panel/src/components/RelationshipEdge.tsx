import { useContext, useRef, type PointerEvent } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
  useReactFlow,
  useStore,
  type EdgeProps,
} from '@xyflow/react'
import { HighlightContext } from '../HighlightContext'
import { EDGE_COLOR, LINK_UP_HANDLE_ID, type GraphEdgeType } from '../graph'

const HIGHLIGHT_EDGE_COLOR = '#f59e0b' // amber — distinct from the normal blue

const ARROW_GAP = 10
const OUTWARD: Record<Position, [number, number]> = {
  [Position.Top]: [0, -1],
  [Position.Bottom]: [0, 1],
  [Position.Left]: [-1, 0],
  [Position.Right]: [1, 0],
}

// How far apart neighbouring parallel edges' control points are pushed.
const PARALLEL_CURVE_BOW = 160

// Only bow edges apart from others running the same way between the same two
// nodes; the opposite direction already uses different handles.
const isGroupMate = (
  edge: { source: string; target: string; sourceHandle?: string | null },
  source: string,
  target: string,
  goesUp: boolean,
) =>
  edge.source === source &&
  edge.target === target &&
  (edge.sourceHandle === LINK_UP_HANDLE_ID) === goesUp

function RelationshipEdge({
  id,
  source,
  target,
  sourceX,
  sourceY,
  targetX: handleX,
  targetY: handleY,
  sourcePosition,
  targetPosition,
  sourceHandleId,
  markerEnd,
  data,
}: EdgeProps<GraphEdgeType>) {
  const { updateEdgeData, screenToFlowPosition } = useReactFlow<
    never,
    GraphEdgeType
  >()
  const dragging = useRef(false)
  const { highlightedEdgeIds } = useContext(HighlightContext)
  const isHighlighted = highlightedEdgeIds.has(id)

  // Stop short of the handle's center so the arrowhead stays visible.
  const [outX, outY] = OUTWARD[targetPosition]
  const targetX = handleX + outX * ARROW_GAP
  const targetY = handleY + outY * ARROW_GAP

  // This edge's position among same-direction parallels, so they bow apart.
  const goesUp = sourceHandleId === LINK_UP_HANDLE_ID
  const parallelIndex = useStore((state) =>
    state.edges
      .filter((edge) => isGroupMate(edge, source, target, goesUp))
      .findIndex((edge) => edge.id === id),
  )
  const parallelCount = useStore(
    (state) =>
      state.edges.filter((edge) => isGroupMate(edge, source, target, goesUp))
        .length,
  )

  // Bow sideways from the straight line between the nodes, measured from a
  // fixed end (smaller id first) so the order is stable.
  const [ax, ay, bx, by] =
    source < target
      ? [sourceX, sourceY, targetX, targetY]
      : [targetX, targetY, sourceX, sourceY]
  const length = Math.hypot(bx - ax, by - ay) || 1
  const bow =
    parallelCount > 1
      ? (Math.max(parallelIndex, 0) - (parallelCount - 1) / 2) *
        PARALLEL_CURVE_BOW
      : 0
  const bowX = (-(by - ay) / length) * bow
  const bowY = ((bx - ax) / length) * bow

  // Leave and arrive along the handles' own direction (so the arrowhead points
  // straight into the node).
  const reach = Math.max(80, length * 0.7)
  const [sourceDirX, sourceDirY] = OUTWARD[sourcePosition]
  const c1X = sourceX + sourceDirX * reach
  const c1Y = sourceY + sourceDirY * reach
  const c2X = targetX + outX * reach
  const c2Y = targetY + outY * reach

  // Default midpoint: a cubic Bézier's midpoint is (S + 3·C1 + 3·C2 + T) / 8.
  const autoX = (sourceX + 3 * c1X + 3 * c2X + targetX) / 8 + bowX * 0.75
  const autoY = (sourceY + 3 * c1Y + 3 * c2Y + targetY) / 8 + bowY * 0.75

  const bend = data?.bend

  let path: string
  let labelX: number
  let labelY: number

  if (parallelCount <= 1 && !bend) {
    ;[path, labelX, labelY] = getBezierPath({
      sourceX,
      sourceY,
      sourcePosition,
      targetX,
      targetY,
      targetPosition,
      curvature: 0.4,
    })
  } else {
    // Shift control points so the midpoint lands on the bowed/dragged position.
    const shiftX = bowX + ((bend?.x ?? 0) * 4) / 3
    const shiftY = bowY + ((bend?.y ?? 0) * 4) / 3
    path =
      `M ${sourceX},${sourceY} ` +
      `C ${c1X + shiftX},${c1Y + shiftY} ${c2X + shiftX},${c2Y + shiftY} ` +
      `${targetX},${targetY}`
    labelX = autoX + (bend?.x ?? 0)
    labelY = autoY + (bend?.y ?? 0)
  }

  // Dragging the dot on the edge moves the middle of the curve under the pointer.
  const onDotPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragging.current = true
  }

  const onDotPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) return
    const pointer = screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    })
    updateEdgeData(id, { bend: { x: pointer.x - autoX, y: pointer.y - autoY } })
  }

  const onDotPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    dragging.current = false
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke: isHighlighted ? HIGHLIGHT_EDGE_COLOR : EDGE_COLOR,
          strokeWidth: isHighlighted ? 3 : 1.5,
        }}
      />
      <EdgeLabelRenderer>
        {/* The label layer ignores pointer events by default, so re-enable them. */}
        <div
          className="nodrag nopan pointer-events-auto absolute"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
        >
          <div
            role="button"
            aria-label="Move edge"
            title="Drag to reshape the edge, double-click to reset"
            onPointerDown={onDotPointerDown}
            onPointerMove={onDotPointerMove}
            onPointerUp={onDotPointerUp}
            onDoubleClick={() => updateEdgeData(id, { bend: undefined })}
            className="size-3.5 cursor-grab touch-none rounded-full border-2 border-white bg-primary-600 shadow active:cursor-grabbing"
          />
          <input
            className="absolute top-4 left-1/2 w-24 -translate-x-1/2 rounded border border-secondary-300 bg-white px-2 py-0.5 text-center text-xs text-gray-800 placeholder:text-gray-400 focus:border-secondary-600 focus:outline-none"
            value={data?.relationship ?? ''}
            onChange={(e) => updateEdgeData(id, { relationship: e.target.value })}
            placeholder="Relationship"
            aria-label="Relationship"
          />
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

export default RelationshipEdge
