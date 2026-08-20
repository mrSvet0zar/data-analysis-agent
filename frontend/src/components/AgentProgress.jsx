import React, { lazy, Suspense, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { openJobSocket } from '../api'
import StepItem from './StepItem'

// Plotly is heavy (~1.5 MB gzip); load it as a separate chunk only when
// there are charts to render, so the initial page stays light.
const ChartGrid = lazy(() => import('./ChartGrid'))

export default function AgentProgress({ jobId, onReset }) {
  const [steps, setSteps] = useState([])
  const [status, setStatus] = useState('running')
  const [result, setResult] = useState(null)
  const [charts, setCharts] = useState([])
  const [report, setReport] = useState(null)
  const [usage, setUsage] = useState(null)
  const [error, setError] = useState(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    // `cancelled` guards against React StrictMode's mount→unmount→remount in dev:
    // the first socket is closed by cleanup before it finishes connecting, which
    // fires a spurious `onerror`. We ignore any event from a socket we're tearing down.
    let cancelled = false
    const ws = openJobSocket(jobId)

    ws.onmessage = (event) => {
      if (cancelled) return
      const data = JSON.parse(event.data)
      if (data.type === 'step') {
        setSteps((prev) => [...prev, data.step])
      } else if (data.type === 'complete') {
        setStatus(data.status)
        setResult(data.result)
        setCharts(data.charts || [])
        setReport(data.report)
        setUsage(data.usage || null)
        if (data.status === 'error') setError(data.error)
      } else if (data.type === 'error') {
        setStatus('error')
        setError(data.message)
      }
    }
    ws.onerror = () => {
      if (cancelled) return
      setError('WebSocket connection failed. Is the backend running?')
    }

    return () => {
      cancelled = true
      ws.close()
    }
  }, [jobId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [steps])

  const running = status === 'running'

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {running ? (
            <span className="flex h-3 w-3">
              <span className="absolute inline-flex h-3 w-3 animate-ping rounded-full bg-indigo-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-indigo-500" />
            </span>
          ) : (
            <span className={`h-3 w-3 rounded-full ${status === 'error' ? 'bg-rose-500' : 'bg-emerald-500'}`} />
          )}
          <h2 className="text-xl font-bold text-slate-100">
            {running ? 'Agent working…' : status === 'error' ? 'Analysis failed' : 'Analysis complete'}
          </h2>
        </div>
        <button
          onClick={onReset}
          className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-white"
        >
          ← New analysis
        </button>
      </div>

      {usage && (usage.input_tokens != null || usage.cost_usd != null) && (
        <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl bg-slate-800/40 px-4 py-3 text-sm ring-1 ring-slate-700">
          <span className="text-slate-400">
            🔢 Tokens{' '}
            <span className="font-mono text-slate-200">
              {(usage.input_tokens || 0).toLocaleString()} in /{' '}
              {(usage.output_tokens || 0).toLocaleString()} out
            </span>
          </span>
          <span className="text-slate-400">
            💰 Est. cost{' '}
            <span className="font-mono text-emerald-300">
              ${Number(usage.cost_usd || 0).toFixed(4)}
            </span>
          </span>
          <span className="text-slate-400">
            🔁 Iterations{' '}
            <span className="font-mono text-slate-200">{usage.iterations ?? '—'}</span>
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Timeline */}
        <div className="lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Agent steps
          </h3>
          <div
            ref={scrollRef}
            className="max-h-[70vh] overflow-y-auto rounded-2xl bg-slate-900/40 p-4 ring-1 ring-slate-800"
          >
            {steps.length === 0 && (
              <p className="text-sm text-slate-500">Waiting for the first step…</p>
            )}
            {steps.map((step, i) => (
              <StepItem key={i} step={step} index={i} />
            ))}
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-3">
          {error && (
            <div className="mb-5 rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
              {error}
            </div>
          )}

          {charts.length > 0 && (
            <div className="mb-6">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Visualizations
              </h3>
              <Suspense
                fallback={
                  <div className="flex h-64 items-center justify-center rounded-2xl bg-slate-900/30 text-sm text-slate-500 ring-1 ring-slate-800">
                    Loading charts…
                  </div>
                }
              >
                <ChartGrid charts={charts} />
              </Suspense>
            </div>
          )}

          {report ? (
            <div>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Report
              </h3>
              <article className="prose-invert rounded-2xl bg-slate-800/40 p-6 ring-1 ring-slate-700">
                <div className="markdown space-y-2 text-slate-200">
                  <ReactMarkdown>{report}</ReactMarkdown>
                </div>
              </article>
            </div>
          ) : (
            result && (
              <div className="rounded-2xl bg-slate-800/40 p-6 ring-1 ring-slate-700">
                <p className="whitespace-pre-wrap text-slate-200">{result}</p>
              </div>
            )
          )}

          {running && charts.length === 0 && !report && (
            <div className="flex h-64 items-center justify-center rounded-2xl bg-slate-900/30 ring-1 ring-slate-800">
              <p className="text-sm text-slate-500">Charts and the report will appear here…</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
