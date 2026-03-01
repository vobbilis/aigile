import { useEffect, useState } from 'react'
import { fetchAlerts, fetchMetrics, type AlertRule, type Metric } from './api'
import { MetricCard } from './components/MetricCard'
import { MetricForm } from './components/MetricForm'
import './alerts.css'

const POLL_INTERVAL_MS = 5000

export default function App() {
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [alerts, setAlerts] = useState<AlertRule[]>([])

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
    } catch {
      // silently ignore alert fetch errors
    }
  }

  useEffect(() => {
    loadMetrics()
    const timer = setInterval(loadMetrics, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    loadAlerts()
    const timer = setInterval(loadAlerts, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="app">
      <header>
        <h1>Metrics Dashboard</h1>
        <span className="poll-indicator">
          polling every {POLL_INTERVAL_MS / 1000}s
        </span>
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

      {alerts.length > 0 && (
        <section className="alerts-panel">
          <h2>Alert Rules</h2>
          <ul className="alerts-list">
            {alerts.map((a) => (
              <li
                key={a.id}
                className={`alert-rule alert-rule--${a.state}`}
              >
                <span className="alert-name">{a.metric_name}</span>
                <span className="alert-condition">
                  {a.operator} {a.threshold}
                </span>
                <span className={`alert-state alert-state--${a.state}`}>
                  {a.state}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
