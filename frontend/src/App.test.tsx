import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import App from './App'
import * as api from './api'

vi.mock('./api')

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.fetchMetrics).mockResolvedValue([])
    vi.mocked(api.fetchAlerts).mockResolvedValue([])
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the dashboard heading', async () => {
    render(<App />)
    expect(screen.getByText('Metrics Dashboard')).toBeInTheDocument()
  })

  it('shows empty state when no metrics', async () => {
    render(<App />)
    expect(
      await screen.findByText('No metrics yet. Submit one above.')
    ).toBeInTheDocument()
  })

  it('renders metrics when returned from API', async () => {
    vi.mocked(api.fetchMetrics).mockResolvedValue([
      {
        id: '1',
        name: 'cpu',
        value: 42.5,
        tags: {},
        timestamp: new Date().toISOString(),
      },
    ])
    render(<App />)
    expect(await screen.findByText('cpu')).toBeInTheDocument()
    expect(await screen.findByText('42.5')).toBeInTheDocument()
  })

  it('renders alerts when returned from API', async () => {
    vi.mocked(api.fetchAlerts).mockResolvedValue([
      {
        id: 'alert-1',
        metric_name: 'cpu',
        operator: 'gt',
        threshold: 80,
        state: 'firing',
        created_at: new Date().toISOString(),
      },
    ])
    render(<App />)
    expect(await screen.findByText('cpu > 80 (firing)')).toBeInTheDocument()
  })

  it('shows empty alerts section when no alerts', async () => {
    render(<App />)
    expect(await screen.findByText('No alerts configured.')).toBeInTheDocument()
  })

  describe('Alert Integration Tests', () => {
    it('polls both metrics and alerts synchronously', async () => {
      vi.useFakeTimers()

      render(<App />)

      // Initial calls should happen immediately
      expect(vi.mocked(api.fetchMetrics)).toHaveBeenCalledTimes(1)
      expect(vi.mocked(api.fetchAlerts)).toHaveBeenCalledTimes(1)

      // After 5 seconds, both should be called again (second time)
      await vi.advanceTimersByTimeAsync(5000)
      expect(vi.mocked(api.fetchMetrics)).toHaveBeenCalledTimes(2)
      expect(vi.mocked(api.fetchAlerts)).toHaveBeenCalledTimes(2)

      // After another 5 seconds, both should be called again (third time)
      await vi.advanceTimersByTimeAsync(5000)
      expect(vi.mocked(api.fetchMetrics)).toHaveBeenCalledTimes(3)
      expect(vi.mocked(api.fetchAlerts)).toHaveBeenCalledTimes(3)
    })

    it('handles alert fetch errors gracefully', async () => {
      vi.mocked(api.fetchAlerts).mockRejectedValue(
        new Error('Alert service down')
      )
      vi.mocked(api.fetchMetrics).mockResolvedValue([
        {
          id: '1',
          name: 'cpu',
          value: 42.5,
          tags: {},
          timestamp: new Date().toISOString(),
        },
      ])

      render(<App />)

      // Metrics should still render correctly despite alert fetch error
      expect(await screen.findByText('cpu')).toBeInTheDocument()
      expect(await screen.findByText('42.5')).toBeInTheDocument()

      // Should show no alerts configured (default state when fetch fails)
      expect(
        await screen.findByText('No alerts configured.')
      ).toBeInTheDocument()
    })

    it('shows firing alert state', async () => {
      vi.mocked(api.fetchAlerts).mockResolvedValue([
        {
          id: 'alert-firing',
          metric_name: 'memory',
          operator: 'gt',
          threshold: 90,
          state: 'firing',
          created_at: new Date().toISOString(),
        },
      ])

      render(<App />)

      expect(
        await screen.findByText('memory > 90 (firing)')
      ).toBeInTheDocument()

      const alertElement = await screen.findByText('memory > 90 (firing)')
      expect(alertElement).toHaveClass('alert-state-firing')
    })
  })

  describe('Tag Filtering', () => {
    it('renders the tag filter input and button', async () => {
      render(<App />)
      expect(
        await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
      ).toBeInTheDocument()
      expect(screen.getByText('Add Filter')).toBeInTheDocument()
    })

    it('shows validation error when tag has no colon', async () => {
      const user = userEvent.setup()
      render(<App />)

      const input = await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
      await user.type(input, 'invalid')
      await user.click(screen.getByText('Add Filter'))

      expect(
        await screen.findByText('Tag must contain a colon (e.g. env:prod)')
      ).toBeInTheDocument()
    })

    it('adds a valid tag chip and passes it to fetchMetrics', async () => {
      const user = userEvent.setup()
      render(<App />)

      const input = await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
      await user.type(input, 'env:prod')
      await user.click(screen.getByText('Add Filter'))

      expect(await screen.findByText('env:prod')).toBeInTheDocument()
      expect(vi.mocked(api.fetchMetrics)).toHaveBeenCalledWith(['env:prod'])
    })

    it('removes a tag chip when clicking remove button', async () => {
      const user = userEvent.setup()
      render(<App />)

      const input = await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
      await user.type(input, 'env:prod')
      await user.click(screen.getByText('Add Filter'))

      expect(await screen.findByText('env:prod')).toBeInTheDocument()

      await user.click(screen.getByLabelText('Remove env:prod'))

      expect(screen.queryByText('env:prod')).not.toBeInTheDocument()
      expect(vi.mocked(api.fetchMetrics)).toHaveBeenLastCalledWith([])
    })
  })

  it('renders Export CSV link with correct attributes', async () => {
    render(<App />)
    
    const exportLink = await screen.findByText('Export CSV')
    expect(exportLink).toBeInTheDocument()
    expect(exportLink).toHaveAttribute('href', '/api/metrics/export?format=csv')
    expect(exportLink).toHaveClass('export-btn')
    expect(exportLink).toHaveAttribute('download', 'metrics.csv')
  })
})
