import React from 'react'

/**
 * Catches render-time errors anywhere below it so a single component failure
 * (e.g. a malformed Plotly figure) shows a recoverable message instead of a
 * blank white screen.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('UI error boundary caught:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto mt-20 max-w-lg rounded-2xl border border-rose-500/40 bg-rose-500/10 p-8 text-center">
          <div className="text-4xl">😵</div>
          <h2 className="mt-3 text-lg font-semibold text-rose-100">Something went wrong</h2>
          <p className="mt-2 text-sm text-rose-200/80">{String(this.state.error)}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-5 rounded-lg bg-rose-500 px-4 py-2 text-sm font-medium text-white hover:bg-rose-400"
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
