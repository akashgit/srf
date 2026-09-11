/**
 * Run one SRF mode end-to-end through the DSH workflow spine.
 *
 * This is SRF's headless execution path: it loads a committed `graph.json`,
 * drives the real spine to `done`, runs every deterministic node as a real
 * subprocess, and calls a real model for every `LLMNode`/`AgentNode`. The ops
 * write their own trace files, and this driver writes a machine-readable
 * `trace.jsonl` (one JSON object per line) plus a final JSON summary.
 *
 * Usage:
 *   node --import tsx/esm srf/tools/science_run.mjs \
 *     --mode gepa --task circle_packing --budget 8 [--provider deepseek]
 *
 * Environment:
 *   DSH_ROOT      the DSH checkout (defaults to the workspace path)
 *   DSH_ENV       the .env with provider keys (defaults to $DSH_ROOT/.env)
 *   SRF_VENV_BIN  the python that has `srf` + `factory` installed
 */

import { pathToFileURL } from 'node:url'
import { existsSync, readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { join, resolve } from 'node:path'
import { parseArgs } from 'node:util'

const WORKSPACE = '/Users/akash/dsh/refactory-dsh'
const DSH_ROOT = process.env.DSH_ROOT ?? join(WORKSPACE, 'deepseek-harness')
const SRF_ROOT = join(WORKSPACE, 'srf')
const VENV_BIN = process.env.SRF_VENV_BIN ?? join(WORKSPACE, '.venv', 'bin')
const ENV_FILE = process.env.DSH_ENV ?? join(DSH_ROOT, '.env')

const SPINE_URL = pathToFileURL(join(DSH_ROOT, 'packages/workflow/workflow-spine/src/spine.ts')).href
const EXECUTE_URL = pathToFileURL(join(DSH_ROOT, 'packages/workflow/workflow-spine/src/execute.ts')).href

const { Spine, validateGraph } = await import(SPINE_URL)
const { isDeterministic, runDeterministic } = await import(EXECUTE_URL)

// ── providers ─────────────────────────────────────────────────────

const PROVIDERS = {
  deepseek: { url: 'https://api.deepseek.com/chat/completions', key: 'DEEPSEEK_API_KEY', model: 'deepseek-v4-pro' },
  openai: { url: 'https://api.openai.com/v1/chat/completions', key: 'OPENAI_API_KEY', model: 'gpt-4o-mini' },
  openrouter: { url: 'https://openrouter.ai/api/v1/chat/completions', key: 'OPENROUTER_API_KEY', model: 'openai/gpt-4o-mini' },
}

function loadEnv() {
  const out = {}
  if (!existsSync(ENV_FILE)) return out
  for (const line of readFileSync(ENV_FILE, 'utf8').split('\n')) {
    const i = line.indexOf('=')
    if (i > 0 && !line.trimStart().startsWith('#')) out[line.slice(0, i).trim()] = line.slice(i + 1).trim()
  }
  return out
}

async function complete(provider, model, { system, user, temperature }) {
  const spec = PROVIDERS[provider]
  if (!spec) throw new Error(`unknown provider ${provider} (known: ${Object.keys(PROVIDERS).join(', ')})`)
  const key = process.env[spec.key] ?? loadEnv()[spec.key]
  if (!key) throw new Error(`no ${spec.key} for provider ${provider}`)
  const messages = []
  if (system) messages.push({ role: 'system', content: system })
  messages.push({ role: 'user', content: user })
  const body = { model: model ?? spec.model, messages, max_tokens: 4000 }
  if (temperature !== undefined) body.temperature = temperature
  const response = await fetch(spec.url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${key}` },
    body: JSON.stringify(body),
  })
  const text = await response.text()
  if (!response.ok) throw new Error(`${provider} ${response.status}: ${text.slice(0, 300)}`)
  const data = JSON.parse(text)
  return data.choices?.[0]?.message?.content ?? ''
}

/** The code inside the first fenced block; the raw text when there is none. */
function extractCode(text) {
  const match = text.match(/```(?:python|py)?\s*\n?([\s\S]*?)(?:\n?```)/)
  return match ? match[1].trimEnd() : text.trim()
}

// ── state files → best score ──────────────────────────────────────

const STATE_FILES = {
  gepa: 'gepa_state.json',
  best_of_n: 'best_of_n_result.json',
  scs: 'scs_state.json',
  aide: 'aide_state.json',
  ai_sci_v1: 'autoresearch_state.json',
  ai_sci_v2: 'aide_state.json',
  openevolve: 'openevolve_state.json',
  shinka: 'shinka_state.json',
  adaevolve: 'adaevolve_state.json',
  evox: 'evox_state.json',
  autoresearch: 'autoresearch_state.json',
  karpathy: 'karpathy_state.json',
  autoscientists: 'autoscientists_state.json',
}

function readBestScore(workdir, mode) {
  const name = STATE_FILES[mode]
  const path = join(workdir, name)
  if (existsSync(path)) {
    try {
      const data = JSON.parse(readFileSync(path, 'utf8'))
      if (typeof data.best_score === 'number') return data.best_score
    } catch { /* not JSON yet */ }
  }
  for (const file of readdirSync(workdir)) {
    if (!file.endsWith('.json')) continue
    try {
      const data = JSON.parse(readFileSync(join(workdir, file), 'utf8'))
      if (typeof data.best_score === 'number') return data.best_score
    } catch { /* ignore */ }
  }
  return 0
}

// ── the run ───────────────────────────────────────────────────────

function shell(workdir, env, timeoutMs) {
  return {
    resolve: (request) => ({
      command: request.command,
      workdir: request.workdir ?? workdir,
      timeoutMs: request.timeoutMs ?? timeoutMs,
      stdoutMaxBytes: 1_000_000,
      env: request.env,
      sandboxPolicy: undefined,
    }),
    run: async (spec) => {
      const started = spawnSync('/bin/sh', ['-c', spec.command], {
        cwd: spec.workdir,
        encoding: 'utf8',
        timeout: spec.timeoutMs,
        env: { ...process.env, ...spec.env },
      })
      return {
        exitCode: started.status,
        signal: started.signal,
        timedOut: started.error !== undefined && started.error.code === 'ETIMEDOUT',
        aborted: false,
        timeoutMs: spec.timeoutMs,
        stdout: { text: started.stdout ?? '', truncated: false },
        stderr: { text: started.stderr ?? '', truncated: false },
      }
    },
  }
}

async function runGraph({ mode, graph, workdir, task, budget, knobs, provider, model, timeoutMs }) {
  const issues = validateGraph(graph)
  if (issues.length > 0) throw new Error(`invalid graph: ${issues.map(i => `${i.node ?? '?'}: ${i.message}`).join('; ')}`)

  // The graph's `model` field is a legacy alias (e.g. "sonnet"); the provider's
  // own model id is what the API needs. `--model` overrides the provider default.
  const modelId = model ?? PROVIDERS[provider]?.model

  mkdirSync(workdir, { recursive: true })
  const env = {
    SRF_WORK_DIR: workdir,
    SRF_TASK: task,
    SRF_KNOBS: JSON.stringify(knobs ?? {}),
    SRF_BUDGET: String(budget),
    PATH: `${VENV_BIN}:${process.env.PATH ?? ''}`,
  }
  const runner = shell(workdir, env, timeoutMs)
  const spine = new Spine(graph, { maxIterations: Math.max(budget * 4, 100) })

  const tracePath = join(workdir, 'trace.jsonl')
  const log = (event) => writeFileSync(tracePath, JSON.stringify(event) + '\n', { flag: 'a' })
  log({ event: 'run', mode, task, budget, provider, model: modelId, workdir })

  let steps = 0
  for (;;) {
    const state = spine.next()
    if (state.status === 'done') break
    if (steps++ > 10_000) throw new Error('run did not converge')
    for (const node of state.nodes ?? []) {
      log({ event: 'node', id: node.id, type: node._type })
      if (isDeterministic(node)) {
        const outcome = await runDeterministic(shell(workdir, env, timeoutMs), node, {
          env,
          timeoutMs,
          ...(workdir === undefined ? {} : { workdir }),
        })
        if (!outcome.ok) {
          throw new Error(`node ${node.id} failed: ${outcome.error} (stderr: ${outcome.stderr.slice(0, 400)})`)
        }
        if (outcome.verdict !== undefined) {
          log({ event: 'gate', id: node.id, verdict: outcome.verdict })
          spine.verdict(node.id, outcome.verdict)
        } else {
          spine.complete(node.id)
        }
      } else if (node._type === 'LLMNode' || node._type === 'AgentNode') {
        const reads = (node.reads ?? []).map(f => readFileSync(join(workdir, f), 'utf8')).join('\n\n')
        const content = await complete(provider, modelId, {
          system: node.prompt_template ?? '',
          user: reads,
          temperature: node.temperature,
        })
        const code = extractCode(content)
        const target = (node.writes ?? [])[0]
        if (target) writeFileSync(join(workdir, target), code)
        log({ event: 'llm', id: node.id, model: modelId, wrote: target ?? null, bytes: code.length })
        spine.complete(node.id)
      } else {
        // Fork / Join and any remaining executable node: the spine owns routing.
        spine.complete(node.id)
      }
    }
  }

  const bestScore = readBestScore(workdir, mode)
  log({ event: 'done', best_score: bestScore, steps })
  return { bestScore, tracePath, workdir }
}

// ── CLI ───────────────────────────────────────────────────────────

function main() {
  const { values } = parseArgs({
    options: {
      mode: { type: 'string', short: 'm' },
      task: { type: 'string', short: 't' },
      budget: { type: 'string', short: 'b', default: '10' },
      provider: { type: 'string', short: 'p', default: 'deepseek' },
      model: { type: 'string' },
      graphs: { type: 'string', default: join(SRF_ROOT, 'graphs') },
      workdir: { type: 'string' },
      knobs: { type: 'string', default: '{}' },
      'timeout-ms': { type: 'string', default: '600000' },
    },
  })
  const mode = values.mode
  const task = values.task
  if (!mode || !task) {
    console.error('usage: science_run.mjs --mode <mode> --task <task> [--budget N] [--provider deepseek|openai|openrouter]')
    process.exit(2)
  }
  const graphPath = join(values.graphs, `${mode}.graph.json`)
  if (!existsSync(graphPath)) {
    console.error(`no graph at ${graphPath}; run \`srf graphs --out ${values.graphs}\` first`)
    process.exit(2)
  }
  const graph = JSON.parse(readFileSync(graphPath, 'utf8'))
  const workdir = values.workdir ?? join(SRF_ROOT, 'outputs', `run-${mode}-${Date.now()}`)
  const budget = Number(values.budget)
  const knobs = JSON.parse(values.knobs)

  runGraph({
    mode,
    graph,
    workdir,
    task,
    budget,
    knobs,
    provider: values.provider,
    model: values.model,
    timeoutMs: Number(values['timeout-ms']),
  }).then(({ bestScore, tracePath, workdir: wd }) => {
    console.log(JSON.stringify({
      mode, task, budget, provider: values.provider, model: values.model ?? PROVIDERS[values.provider]?.model,
      best_score: bestScore, trace: tracePath, workdir: wd,
    }, null, 2))
  }).catch((error) => {
    console.error(`science run failed: ${error instanceof Error ? error.message : String(error)}`)
    process.exit(1)
  })
}

main()
