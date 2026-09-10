/**
 * Walk every emitted SRF graph through the real DSH workflow spine.
 *
 * This is the boundary test for SRF's graph IR: it loads `graph.json` exactly as
 * the runtime does, validates it, then drives the spine to completion — choosing
 * a verdict at every gate — and reports which nodes were never reached.
 *
 * Usage:
 *   node --import tsx/esm srf/tools/spine_probe.mjs <graph.json> [...]
 *
 * Environment:
 *   SRF_SPINE_MODULE  file: URL of the spine module to load. Defaults to the
 *                     workflow-spine source inside the DSH checkout.
 *   SRF_GATE_LOOPS    How many times a gate is asked to reloop before it is
 *                     asked to proceed. Default 3.
 */

import { pathToFileURL } from 'node:url'

const DEFAULT_SPINE = pathToFileURL(
  '/Users/akash/dsh/refactory-dsh/deepseek-harness/packages/workflow/workflow-spine/src/spine.ts',
).href

const STEP_LIMIT = 20000

/** Walk one graph to completion, exercising every gate outcome in turn. */
function walk(graph, loopsPerGate, Spine, validateGraph) {
  const issues = validateGraph(graph)
  const result = {
    name: graph.name ?? null,
    nodes: Object.keys(graph.nodes).length,
    edges: graph.edges.length,
    issues,
    ok: false,
    steps: 0,
    reached: [],
    missed: [],
    error: null,
  }
  if (issues.length > 0) return result

  const spine = new Spine(graph, { maxIterations: loopsPerGate + 1 })
  const reached = new Set()
  const visits = new Map()
  try {
    for (let step = 0; step < STEP_LIMIT; step += 1) {
      const state = spine.next()
      if (state.status === 'done') {
        result.steps = step
        result.ok = true
        break
      }
      for (const node of state.nodes ?? []) {
        reached.add(node.id)
        if (node._type !== 'GateNode') {
          spine.complete(node.id)
          continue
        }
        const verdicts = node.verdicts ?? []
        const seen = visits.get(node.id) ?? 0
        visits.set(node.id, seen + 1)
        spine.verdict(node.id, chooseVerdict(verdicts, seen, loopsPerGate), 'spine-probe')
      }
    }
  } catch (error) {
    result.error = String(error)
  }
  result.reached = [...reached].sort()
  result.missed = Object.keys(graph.nodes).filter(id => !reached.has(id)).sort()
  return result
}

/**
 * Pick a verdict that keeps the walk moving and still covers the gate's branches.
 *
 * A gate that offers `reloop` is a study loop: reloop a bounded number of times,
 * then take a forward outcome. Among forward outcomes the choice rotates, so a
 * switch gate's alternative branches are all exercised rather than only the
 * first one.
 */
function chooseVerdict(verdicts, seen, loopsPerGate) {
  const forward = verdicts.filter(verdict => verdict !== 'reloop')
  if (verdicts.includes('reloop') && seen < loopsPerGate) return 'reloop'
  if (forward.length === 0) return verdicts[0] ?? 'proceed'
  return forward[seen % forward.length]
}

const paths = process.argv.slice(2)
if (paths.length === 0) {
  console.error('Usage: spine_probe.mjs <graph.json> [...]')
  process.exit(2)
}

const moduleUrl = process.env.SRF_SPINE_MODULE ?? DEFAULT_SPINE
const { Spine, validateGraph } = await import(moduleUrl)
const loopsPerGate = Number(process.env.SRF_GATE_LOOPS ?? '3')

const report = []
for (const path of paths) {
  const graph = JSON.parse(await (await import('node:fs/promises')).readFile(path, 'utf8'))
  report.push({ path, ...walk(graph, loopsPerGate, Spine, validateGraph) })
}

console.log(JSON.stringify(report, null, 2))
const failed = report.filter(entry => !entry.ok || entry.missed.length > 0)
process.exit(failed.length === 0 ? 0 : 1)
