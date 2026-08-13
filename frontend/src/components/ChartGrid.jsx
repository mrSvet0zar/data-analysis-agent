import React from 'react'
import Plot from 'react-plotly.js'

export default function ChartGrid({ charts }) {
  if (!charts?.length) return null

  const darkLayout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#cbd5e1' },
    margin: { l: 50, r: 20, t: 50, b: 40 },
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      {charts.map((chart, i) => {
        const fig = chart.plotly_json || {}
        return (
          <div key={i} className="rounded-2xl bg-slate-800/40 p-3 ring-1 ring-slate-700">
            <Plot
              data={fig.data || []}
              layout={{ ...(fig.layout || {}), ...darkLayout, autosize: true }}
              useResizeHandler
              style={{ width: '100%', height: '340px' }}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        )
      })}
    </div>
  )
}
