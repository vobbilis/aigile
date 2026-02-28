import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from './App'
import * as api from './api'

vi.mock('./api')

describe('App', () => {
  beforeEach(() => {
    vi.mocked(api.fetchMetrics).mockResolvedValue([])
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
})
