import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StepItem from './StepItem'

describe('StepItem', () => {
  it('renders a tool_result with its summary and tool name', () => {
    render(
      <StepItem
        step={{ type: 'tool_result', tool: 'read_csv', success: true, summary: '300 rows × 6 columns' }}
        index={0}
      />
    )
    expect(screen.getByText('read_csv')).toBeInTheDocument()
    expect(screen.getByText('300 rows × 6 columns')).toBeInTheDocument()
    expect(screen.getByText('Result')).toBeInTheDocument()
  })

  it('renders tool_use input as JSON', () => {
    render(
      <StepItem
        step={{ type: 'tool_use', tool: 'detect_outliers', input: { method: 'iqr', column: 'revenue' } }}
        index={1}
      />
    )
    expect(screen.getByText('detect_outliers')).toBeInTheDocument()
    expect(screen.getByText(/"method": "iqr"/)).toBeInTheDocument()
  })

  it('marks a failed tool_result', () => {
    render(
      <StepItem
        step={{ type: 'tool_result', tool: 'create_visualization', success: false, summary: 'error: bad column' }}
        index={2}
      />
    )
    expect(screen.getByText('error: bad column')).toBeInTheDocument()
  })
})
