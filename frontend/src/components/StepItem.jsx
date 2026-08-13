import React from 'react'

const META = {
  thinking: { icon: '💭', label: 'Reasoning', color: 'text-slate-300' },
  tool_use: { icon: '🔧', label: 'Tool call', color: 'text-indigo-300' },
  tool_result: { icon: '✅', label: 'Result', color: 'text-emerald-300' },
  completion: { icon: '🏁', label: 'Done', color: 'text-emerald-400' },
  error: { icon: '⚠️', label: 'Error', color: 'text-rose-400' },
}

export default function StepItem({ step, index }) {
  const meta = META[step.type] || { icon: '•', label: step.type, color: 'text-slate-300' }
  const failed = step.type === 'tool_result' && step.success === false

  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-800 text-sm ring-1 ring-slate-700">
          {meta.icon}
        </div>
        <div className="mt-1 w-px flex-1 bg-slate-700/70" />
      </div>

      <div className="pb-5">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold uppercase tracking-wide ${failed ? 'text-rose-400' : meta.color}`}>
            {meta.label}
          </span>
          {step.tool && (
            <span className="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-xs text-indigo-300 ring-1 ring-slate-700">
              {step.tool}
            </span>
          )}
        </div>

        {step.type === 'tool_use' && step.input && Object.keys(step.input).length > 0 && (
          <pre className="mt-1 overflow-x-auto rounded-lg bg-slate-900/70 p-2 font-mono text-xs text-slate-400 ring-1 ring-slate-800">
            {JSON.stringify(step.input, null, 2)}
          </pre>
        )}

        {step.type === 'tool_result' && (
          <p className={`mt-1 text-sm ${failed ? 'text-rose-300' : 'text-slate-300'}`}>
            {step.summary}
          </p>
        )}

        {(step.type === 'thinking' || step.type === 'completion') && step.message && (
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-300">{step.message}</p>
        )}

        {step.type === 'error' && <p className="mt-1 text-sm text-rose-300">{step.message}</p>}
      </div>
    </div>
  )
}
