import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchMetrics,
  fetchMetricHistory,
  fetchAlerts,
  createAlert,
  deleteAlert,
  type AlertRuleIn,
  type AlertRule,
} from './api'

// Mock fetch globally
const mockFetch = vi.fn<typeof fetch>()
vi.stubGlobal('fetch', mockFetch)

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchMetrics with tags', () => {
    it('should fetch metrics without tags when none provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      } as Response)

      await fetchMetrics()

      expect(mockFetch).toHaveBeenCalledWith('/api/metrics')
    })

    it('should fetch metrics without tags when empty array provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      } as Response)

      await fetchMetrics([])

      expect(mockFetch).toHaveBeenCalledWith('/api/metrics')
    })

    it('should append single tag query parameter', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      } as Response)

      await fetchMetrics(['env:prod'])

      expect(mockFetch).toHaveBeenCalledWith('/api/metrics?tag=env%3Aprod')
    })

    it('should append multiple tag query parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      } as Response)

      await fetchMetrics(['env:prod', 'host:server1'])

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/metrics?tag=env%3Aprod&tag=host%3Aserver1'
      )
    })
  })

  describe('fetchAlerts', () => {
    it('should fetch alerts', async () => {
      const mockAlerts = [
        {
          id: 'a1',
          metric_name: 'cpu',
          operator: 'gt',
          threshold: 90,
          state: 'firing',
          created_at: '2026-02-28T10:00:00Z',
        },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockAlerts),
      } as Response)

      const result = await fetchAlerts()

      expect(mockFetch).toHaveBeenCalledWith('/api/alerts')
      expect(result).toEqual(mockAlerts)
    })

    it('should throw error when response is not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response)

      await expect(fetchAlerts()).rejects.toThrow('Failed to fetch alerts: 500')
    })
  })

  describe('fetchMetricHistory', () => {
    it('should fetch metric history with default limit', async () => {
      const mockMetrics = [
        {
          id: '1',
          name: 'cpu',
          value: 42.5,
          tags: { host: 'server1' },
          timestamp: '2026-02-28T10:00:00Z',
        },
        {
          id: '2',
          name: 'cpu',
          value: 45.2,
          tags: { host: 'server1' },
          timestamp: '2026-02-28T10:01:00Z',
        },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockMetrics),
      } as Response)

      const result = await fetchMetricHistory('cpu')

      expect(mockFetch).toHaveBeenCalledWith('/api/metrics/cpu/history?limit=20')
      expect(result).toEqual(mockMetrics)
    })

    it('should fetch metric history with custom limit', async () => {
      const mockMetrics = [
        {
          id: '1',
          name: 'memory',
          value: 80.5,
          tags: { host: 'server2' },
          timestamp: '2026-02-28T10:00:00Z',
        },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockMetrics),
      } as Response)

      const result = await fetchMetricHistory('memory', 5)

      expect(mockFetch).toHaveBeenCalledWith('/api/metrics/memory/history?limit=5')
      expect(result).toEqual(mockMetrics)
    })

    it('should throw error when response is not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response)

      await expect(fetchMetricHistory('nonexistent')).rejects.toThrow(
        'Failed to fetch metric history: 404'
      )
    })
  })

  describe('createAlert', () => {
    it('should create an alert', async () => {
      const alertIn: AlertRuleIn = {
        metric_name: 'cpu',
        operator: 'gt',
        threshold: 80,
      }

      const alertOut: AlertRule = {
        id: 'alert-1',
        metric_name: 'cpu',
        operator: 'gt',
        threshold: 80,
        state: 'ok',
        created_at: '2026-02-28T10:00:00Z',
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(alertOut),
      } as Response)

      const result = await createAlert(alertIn)

      expect(mockFetch).toHaveBeenCalledWith('/api/alerts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(alertIn),
      })
      expect(result).toEqual(alertOut)
    })

    it('should throw error when status is not 201', async () => {
      const alertIn: AlertRuleIn = {
        metric_name: 'cpu',
        operator: 'gt',
        threshold: 80,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
      } as Response)

      await expect(createAlert(alertIn)).rejects.toThrow('Failed to create alert: 200')
    })

    it('should throw error when response is not ok', async () => {
      const alertIn: AlertRuleIn = {
        metric_name: 'cpu',
        operator: 'gt',
        threshold: 80,
      }

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
      } as Response)

      await expect(createAlert(alertIn)).rejects.toThrow('Failed to create alert: 400')
    })
  })

  describe('deleteAlert', () => {
    it('should delete an alert', async () => {
      const deleteResult = { deleted: 1 }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(deleteResult),
      } as Response)

      const result = await deleteAlert('alert-1')

      expect(mockFetch).toHaveBeenCalledWith('/api/alerts/alert-1', { method: 'DELETE' })
      expect(result).toEqual(deleteResult)
    })

    it('should throw error when response is not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response)

      await expect(deleteAlert('alert-1')).rejects.toThrow('Failed to delete alert: 500')
    })
  })
})