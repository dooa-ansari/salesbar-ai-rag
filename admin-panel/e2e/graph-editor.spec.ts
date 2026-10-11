import { expect, test } from '@playwright/test'
import { json, mockApi } from './fixtures'

test('creating a node and saving a new graph sends the right payload', async ({ page }) => {
  let savedBody: Record<string, unknown> | null = null

  await mockApi(page, {
    'POST /graphs': async (route) => {
      savedBody = route.request().postDataJSON()
      await json(route, {
        message: 'Graph saved successfully',
        status: 'success',
        id: 'new-graph-id',
        name: savedBody!.name,
        nodes: (savedBody!.nodes as unknown[]).length,
        edges: 0,
      })
    },
    // Saving a brand-new graph moves the URL onto its real id (see
    // GraphEditorPage's saveGraph), which re-triggers the load effect.
    'GET /graphs/new-graph-id': (route) =>
      json(route, {
        id: 'new-graph-id',
        name: savedBody!.name,
        text: null,
        nodes: savedBody!.nodes,
        edges: savedBody!.edges,
      }),
  })

  await page.goto('/graphs/new')

  await page.getByRole('button', { name: 'Add node' }).click()
  await page.getByLabel('Name', { exact: true }).fill('Robert Smith')
  await page.getByLabel('Type', { exact: true }).fill('Person')
  await page.getByLabel('Graph name').fill('My Family')

  await page.getByRole('button', { name: 'Save graph' }).click()

  await expect(page.getByText(/Saved "My Family"/)).toBeVisible()
  await expect(page).toHaveURL(/\/graphs\/new-graph-id$/)

  expect(savedBody).not.toBeNull()
  expect(savedBody!.name).toBe('My Family')
  expect(savedBody!.nodes).toHaveLength(1)
  expect((savedBody!.nodes as Array<{ data: { name: string; type: string } }>)[0].data).toMatchObject({
    name: 'Robert Smith',
    type: 'Person',
  })
})

test('loading an existing graph renders its nodes and the edge label', async ({ page }) => {
  await mockApi(page, {
    'GET /graphs/g1': (route) =>
      json(route, {
        id: 'g1',
        name: 'Smith Family Tree',
        text: null,
        nodes: [
          {
            id: 'robert',
            type: 'graph',
            position: { x: 0, y: 0 },
            data: { name: 'Robert Smith', type: 'Person', properties: [] },
          },
          {
            id: 'james',
            type: 'graph',
            position: { x: 400, y: 300 },
            data: { name: 'James Smith', type: 'Person', properties: [] },
          },
        ],
        edges: [
          { id: 'e1', source: 'robert', target: 'james', relationship: 'Father' },
        ],
      }),
  })

  await page.goto('/graphs/g1')

  await expect(page.getByLabel('Graph name')).toHaveValue('Smith Family Tree')
  await expect(page.getByLabel('Name', { exact: true }).first()).toHaveValue('Robert Smith')
  await expect(page.getByLabel('Relationship')).toHaveValue('Father')
})

test('deleting a node removes it and its edges, after confirming', async ({ page }) => {
  await mockApi(page, {
    'GET /graphs/g1': (route) =>
      json(route, {
        id: 'g1',
        name: 'Smith Family Tree',
        text: null,
        nodes: [
          {
            id: 'robert',
            type: 'graph',
            position: { x: 0, y: 0 },
            data: { name: 'Robert Smith', type: 'Person', properties: [] },
          },
          {
            id: 'james',
            type: 'graph',
            position: { x: 400, y: 300 },
            data: { name: 'James Smith', type: 'Person', properties: [] },
          },
        ],
        edges: [
          { id: 'e1', source: 'robert', target: 'james', relationship: 'Father' },
        ],
      }),
  })

  await page.goto('/graphs/g1')
  await expect(page.locator('[data-id="robert"]')).toBeVisible()

  // Dismissing the confirmation leaves the node (and its edge) in place.
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.locator('[data-id="robert"]').getByRole('button', { name: 'Delete node' }).click()
  await expect(page.locator('[data-id="robert"]')).toBeVisible()
  await expect(page.locator('.react-flow__edge')).toHaveCount(1)

  // Accepting it removes the node and the edge that connected it.
  page.once('dialog', (dialog) => dialog.accept())
  await page.locator('[data-id="robert"]').getByRole('button', { name: 'Delete node' }).click()
  await expect(page.locator('[data-id="robert"]')).toHaveCount(0)
  await expect(page.locator('[data-id="james"]')).toBeVisible()
  await expect(page.locator('.react-flow__edge')).toHaveCount(0)
})

test('deleting a node flags the generated text and embeddings as stale', async ({ page }) => {
  await mockApi(page, {
    'GET /graphs/g1': (route) =>
      json(route, {
        id: 'g1',
        name: 'Smith Family Tree',
        // Matches what humanizeGraph() computes for the two nodes below, so
        // nothing looks stale right after load.
        text: 'Robert Smith is a person. James Smith is a person.',
        nodes: [
          {
            id: 'robert',
            type: 'graph',
            position: { x: 0, y: 0 },
            data: { name: 'Robert Smith', type: 'Person', properties: [] },
            embeddingDimensions: 1024,
          },
          {
            id: 'james',
            type: 'graph',
            position: { x: 400, y: 300 },
            data: { name: 'James Smith', type: 'Person', properties: [] },
            embeddingDimensions: 1024,
          },
        ],
        edges: [
          { id: 'e1', source: 'robert', target: 'james', relationship: 'Father' },
        ],
      }),
  })

  await page.goto('/graphs/g1')
  await expect(page.locator('[data-id="robert"]')).toBeVisible()
  await expect(page.getByText(/the graph changed since/i)).not.toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  await page.locator('[data-id="robert"]').getByRole('button', { name: 'Delete node' }).click()

  await expect(page.getByText('The graph changed since the text and embeddings were generated')).toBeVisible()
})

test('loading a graph auto-arranges nodes that start on top of each other', async ({ page }) => {
  const sameSpotNodes = Array.from({ length: 4 }, (_, i) => ({
    id: `n${i}`,
    type: 'graph',
    position: { x: 0, y: 0 }, // deliberately identical — a congested/overlapping start
    data: { name: `Node ${i}`, type: 'Thing', properties: [] },
  }))

  await mockApi(page, {
    'GET /graphs/g1': (route) =>
      json(route, { id: 'g1', name: 'Congested', text: null, nodes: sameSpotNodes, edges: [] }),
  })

  await page.goto('/graphs/g1')
  await expect(page.locator('[data-id="n0"]')).toBeVisible()
  // The fitView animation triggered by the on-load auto-arrange.
  await page.waitForTimeout(500)

  const positionsAfterLoad = await Promise.all(
    sameSpotNodes.map((n) => page.locator(`[data-id="${n.id}"]`).boundingBox()),
  )
  const uniqueXYAfterLoad = new Set(
    positionsAfterLoad.map((box) => `${Math.round(box!.x)},${Math.round(box!.y)}`),
  )
  expect(uniqueXYAfterLoad.size).toBe(sameSpotNodes.length)

  // The manual button still works too, e.g. after the user drags nodes back on top of each other.
  await page.getByRole('button', { name: 'Auto-arrange' }).click()
  await page.waitForTimeout(500)

  const positionsAfterClick = await Promise.all(
    sameSpotNodes.map((n) => page.locator(`[data-id="${n.id}"]`).boundingBox()),
  )
  const uniqueXYAfterClick = new Set(
    positionsAfterClick.map((box) => `${Math.round(box!.x)},${Math.round(box!.y)}`),
  )
  expect(uniqueXYAfterClick.size).toBe(sameSpotNodes.length)
})
