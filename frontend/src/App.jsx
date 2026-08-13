import React, { useState } from 'react'
import CSVUpload from './components/CSVUpload'
import AgentProgress from './components/AgentProgress'
import { startAnalysis } from './api'

export default function App() {
  const [jobId, setJobId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleUpload = async (file, requestText) => {
    setLoading(true)
    setError(null)
    try {
      const data = await startAnalysis(file, requestText)
      setJobId(data.job_id)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setJobId(null)
    setError(null)
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <header className="mb-10 text-center">
          <h1 className="bg-gradient-to-r from-indigo-400 to-fuchsia-400 bg-clip-text text-4xl font-extrabold text-transparent">
            🤖 Data Analysis Agent
          </h1>
          <p className="mt-2 text-slate-400">
            Upload a CSV and watch an autonomous agent explore it, step by step.
          </p>
        </header>

        {error && (
          <div className="mx-auto mb-6 max-w-2xl rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-center text-sm text-rose-200">
            {error}
          </div>
        )}

        {!jobId ? (
          <CSVUpload onUpload={handleUpload} loading={loading} />
        ) : (
          <AgentProgress jobId={jobId} onReset={reset} />
        )}

        <footer className="mt-16 text-center text-xs text-slate-600">
          FastAPI · Claude tool-use · React · Plotly · WebSockets
        </footer>
      </div>
    </div>
  )
}
