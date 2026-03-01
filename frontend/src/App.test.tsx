import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from './App'
import * as api from './api'

vi.mock('./api')

describe('App', () => {
  beforeEach(() => {
    vi.mocked(api.fetchMetrics).mockResolvedValue([])
    vi.mocked(api.fetchAlerts).mockResolvedValue([])
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

  it('renders alerts panel when alerts are returned', async () => {
    vi.mocked(api.fetchAlerts).mockResolvedValue([
      {
        id: 'a1',
        metric_name: 'cpu',
        operator: 'gt',
        threshold: 90,
        state: 'firing',
        created_at: new Date().toISOString(),
      },
      {
        id: 'a2',
        metric_name: 'memory',
        operator: 'lt',
        threshold: 20,
        state: 'ok',
        created_at: new Date().toISOString(),
      },
    ])
    render(<App />)
    expect(await screen.findByText('Alert Rules')).toBeInTheDocument()
    expect(await screen.findByText('firing')).toBeInTheDocument()
    expect(await screen.findByText('ok')).toBeInTheDocument()
  })

  it('does not render alerts panel when no alerts', async () => {
    render(<App />)
    await screen.findByText('No metrics yet. Submit one above.')
    expect(screen.queryByText('Alert Rules')).not.toBeInTheDocument()
  })
})
