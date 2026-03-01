import { useEffect, useState } from 'react'
import { fetchAlerts, fetchMetrics, type AlertRule, type Metric } from './api'
import { MetricCard } from './components/MetricCard'
import { MetricForm } from './components/MetricForm'
import './alerts.css'

const POLL_INTERVAL_MS = 5000

export default function App() {
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [alerts, setAlerts] = useState<AlertRule[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const loadMetrics = async () => {
    try {
      const data = await fetchMetrics()
      setMetrics(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const loadAlerts = async () => {
    try {
      const data = await fetchAlerts()
      setAlerts(data)
    } catch (e) {
      // Alert errors should NOT break metrics polling - handle independently
      console.error('Failed to load alerts:', e)
    }
  }

  useEffect(() => {
    const loadData = async () => {
      await Promise.all([loadMetrics(), loadAlerts()])
    }
    loadData()
    const timer = setInterval(loadData, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="app">
      <header>
        <h1>Metrics Dashboard</h1>
        <span className="poll-indicator">
          polling every {POLL_INTERVAL_MS / 1000}s
        </span>
        <a href="/api/metrics/export?format=csv" className="export-btn" download="metrics.csv">
          Export CSV
        </a>
      </header>

      <MetricForm onSubmit={loadMetrics} />

      {loading && <p className="status">Loading...</p>}
      {error && <p className="error">Error: {error}</p>}

      {!loading && metrics.length === 0 && (
        <p className="status">No metrics yet. Submit one above.</p>
      )}

      <div className="metric-grid">
        {metrics.map((m) => (
          <MetricCard key={m.id} metric={m} onDelete={loadMetrics} />
        ))}
      </div>

      <div className="alert-list">
        <h2>Alerts</h2>
        {alerts.length === 0 ? (
          <p>No alerts configured.</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`alert-item ${alert.state === 'firing' ? 'alert-state-firing' : ''}`}
            >
              {alert.metric_name}{' '}
              {alert.operator === 'gt'
                ? '>'
                : alert.operator === 'lt'
                  ? '<'
                  : '='}{' '}
              {alert.threshold} ({alert.state})
            </div>
          ))
        )}
      </div>
    </div>
  )
}
