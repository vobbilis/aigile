import { describe, it, expect, vi, beforeEach } from 'vitest'
import { 
  fetchMetricHistory,
  fetchAlerts, 
  createAlert, 
  deleteAlert,
  AlertRuleIn,
  AlertRuleOut
} from './api'

// Mock fetch globally
const mockFetch = vi.fn() as any
vi.stubGlobal('fetch', mockFetch)

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
        json: () => Promise.resolve(mockMetrics),
      })

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
        json: () => Promise.resolve(mockMetrics),
      })

      const result = await fetchMetricHistory('memory', 5)

      expect(mockFetch).toHaveBeenCalledWith('/api/metrics/memory/history?limit=5')
      expect(result).toEqual(mockMetrics)
    })

    it('should throw error when response is not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      })

      await expect(fetchMetricHistory('nonexistent')).rejects.toThrow(
        'Failed to fetch metric history: 404'
      )
    })
  })

  describe('fetchAlerts', () => {
    it('should fetch alerts', async () => {
      const mockAlerts: AlertRuleOut[] = [
        {
          id: 'alert-1',
          metric_name: 'cpu',
          operator: 'gt',
          threshold: 80,
          state: 'ok',
          created_at: '2026-02-28T10:00:00Z',
        },
        {
          id: 'alert-2',
          metric_name: 'memory',
          operator: 'lt',
          threshold: 20,
          state: 'firing',
          created_at: '2026-02-28T10:01:00Z',
        },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAlerts),
      })

      const result = await fetchAlerts()

      expect(mockFetch).toHaveBeenCalledWith('/api/alerts')
      expect(result).toEqual(mockAlerts)
    })

    it('should throw error when response is not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      await expect(fetchAlerts()).rejects.toThrow('Failed to fetch alerts: 500')
    })
  })

  describe('createAlert', () => {
    it('should create an alert', async () => {
      const alertIn: AlertRuleIn = {
        metric_name: 'cpu',
        operator: 'gt',
        threshold: 80,
      }

      const alertOut: AlertRuleOut = {
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
      })

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
      })

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
      })

      await expect(createAlert(alertIn)).rejects.toThrow('Failed to create alert: 400')
    })
  })

  describe('deleteAlert', () => {
    it('should delete an alert', async () => {
      const deleteResult = { deleted: 1 }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(deleteResult),
      })

      const result = await deleteAlert('alert-1')

      expect(mockFetch).toHaveBeenCalledWith('/api/alerts/alert-1', { method: 'DELETE' })
      expect(result).toEqual(deleteResult)
    })

    it('should throw error when response is not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      await expect(deleteAlert('alert-1')).rejects.toThrow('Failed to delete alert: 500')
    })
  })
})