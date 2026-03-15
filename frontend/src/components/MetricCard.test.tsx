import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MetricCard } from './MetricCard'
import * as api from '../api'

vi.mock('../api')

// Mock recharts ResponsiveContainer for jsdom
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 150, height: 60 }}>{children}</div>
    ),
  }
})

const mockMetric: api.Metric = {
  id: '1',
  name: 'cpu',
  value: 42.5,
  tags: { host: 'server1' },
  timestamp: '2026-03-15T10:00:00Z',
}

describe('MetricCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders metric name and value', () => {
    vi.mocked(api.fetchMetricHistory).mockResolvedValue([])
    render(<MetricCard metric={mockMetric} onDelete={vi.fn()} />)
    expect(screen.getByText('cpu')).toBeInTheDocument()
    expect(screen.getByText('42.5')).toBeInTheDocument()
  })

  it('calls fetchMetricHistory on mount', () => {
    vi.mocked(api.fetchMetricHistory).mockResolvedValue([])
    render(<MetricCard metric={mockMetric} onDelete={vi.fn()} />)
    expect(api.fetchMetricHistory).toHaveBeenCalledWith('cpu')
  })

  it('renders sparkline when history data is available', async () => {
    vi.mocked(api.fetchMetricHistory).mockResolvedValue([
      { id: '1', name: 'cpu', value: 40, tags: {}, timestamp: '2026-03-15T09:58:00Z' },
      { id: '2', name: 'cpu', value: 42, tags: {}, timestamp: '2026-03-15T09:59:00Z' },
      { id: '3', name: 'cpu', value: 42.5, tags: {}, timestamp: '2026-03-15T10:00:00Z' },
    ])
    const { container } = render(<MetricCard metric={mockMetric} onDelete={vi.fn()} />)
    await waitFor(() => {
      expect(container.querySelector('.metric-sparkline')).not.toBeNull()
    })
  })

  it('does not render sparkline when history is empty', async () => {
    vi.mocked(api.fetchMetricHistory).mockResolvedValue([])
    const { container } = render(<MetricCard metric={mockMetric} onDelete={vi.fn()} />)
    await waitFor(() => {
      expect(api.fetchMetricHistory).toHaveBeenCalled()
    })
    expect(container.querySelector('.metric-sparkline')).toBeNull()
  })

  it('does not render sparkline when history fetch fails', async () => {
    vi.mocked(api.fetchMetricHistory).mockRejectedValue(new Error('Not found'))
    const { container } = render(<MetricCard metric={mockMetric} onDelete={vi.fn()} />)
    await waitFor(() => {
      expect(api.fetchMetricHistory).toHaveBeenCalled()
    })
    expect(container.querySelector('.metric-sparkline')).toBeNull()
  })

  it('renders delete button with correct aria label', () => {
    vi.mocked(api.fetchMetricHistory).mockResolvedValue([])
    render(<MetricCard metric={mockMetric} onDelete={vi.fn()} />)
    expect(screen.getByLabelText('Delete cpu')).toBeInTheDocument()
  })

  it('renders metric tags', () => {
    vi.mocked(api.fetchMetricHistory).mockResolvedValue([])
    render(<MetricCard metric={mockMetric} onDelete={vi.fn()} />)
    expect(screen.getByText('host=server1')).toBeInTheDocument()
  })
})
