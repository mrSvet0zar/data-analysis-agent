import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'

const PRESETS = [
  'Analyze this data and provide the key insights.',
  'Find correlations and anomalies in this dataset.',
  'Summarize the data quality and highlight any issues.',
]

export default function CSVUpload({ onUpload, loading }) {
  const [file, setFile] = useState(null)
  const [requestText, setRequestText] = useState(PRESETS[0])
  const [error, setError] = useState(null)

  const onDrop = useCallback((accepted, rejected) => {
    setError(null)
    if (rejected?.length) {
      setError('Please drop a single .csv file.')
      return
    }
    if (accepted?.length) setFile(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    maxFiles: 1,
    multiple: false,
  })

  const submit = () => {
    if (!file) {
      setError('Select a CSV file first.')
      return
    }
    onUpload(file, requestText)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div
        {...getRootProps()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition
          ${isDragActive ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-600 bg-slate-800/40 hover:border-slate-500'}`}
      >
        <input {...getInputProps()} />
        <div className="text-5xl">📄</div>
        <p className="mt-3 text-lg font-semibold text-slate-100">
          {file ? file.name : 'Drop a CSV here, or click to browse'}
        </p>
        <p className="mt-1 text-sm text-slate-400">
          {file
            ? `${(file.size / 1024).toFixed(1)} KB · ready to analyze`
            : 'Max 50 MB · .csv only'}
        </p>
      </div>

      <label className="mt-6 block text-sm font-medium text-slate-300">
        What should the agent do?
      </label>
      <textarea
        value={requestText}
        onChange={(e) => setRequestText(e.target.value)}
        rows={2}
        className="mt-2 w-full resize-none rounded-xl border border-slate-700 bg-slate-800/60 p-3 text-slate-100 outline-none focus:border-indigo-400"
      />
      <div className="mt-2 flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p}
            onClick={() => setRequestText(p)}
            className="rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 text-xs text-slate-300 hover:border-indigo-400 hover:text-white"
          >
            {p}
          </button>
        ))}
      </div>

      {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}

      <button
        onClick={submit}
        disabled={loading}
        className="mt-6 w-full rounded-xl bg-indigo-500 py-3 text-base font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? 'Starting…' : '🚀 Run the agent'}
      </button>
    </div>
  )
}
