import { useEffect, useState } from 'react'
import { deleteMetric, fetchMetricHistory, type Metric } from '../api'
import { SparklineChart } from './SparklineChart'

interface Props {
  metric: Metric
  onDelete: () => void
}

export function MetricCard({ metric, onDelete }: Props) {
  const [historyData, setHistoryData] = useState<{ value: number }[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const loadHistory = async () => {
      try {
        const history = await fetchMetricHistory(metric.name)
        if (!cancelled) {
          setHistoryData(history.map((m) => ({ value: m.value })))
        }
      } catch {
        if (!cancelled) {
          setHistoryData([])
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false)
        }
      }
    }
    loadHistory()
    return () => {
      cancelled = true
    }
  }, [metric.name])

  const handleDelete = async () => {
    try {
      await deleteMetric(metric.name)
      onDelete()
    } catch (err) {
      console.error('Failed to delete metric:', err)
    }
  }

  return (
    <div className="metric-card">
      <div className="metric-header">
        <span className="metric-name">{metric.name}</span>
        <button onClick={handleDelete} aria-label={`Delete ${metric.name}`}>
          ×
        </button>
      </div>
      <div className="metric-value">{metric.value}</div>
      {!historyLoading && historyData.length > 0 && (
        <div className="metric-sparkline">
          <SparklineChart data={historyData} />
        </div>
      )}
      <div className="metric-meta">
        <span>{new Date(metric.timestamp).toLocaleTimeString()}</span>
        {Object.entries(metric.tags).map(([k, v]) => (
          <span key={k} className="tag">
            {k}={v}
          </span>
        ))}
      </div>
    </div>
  )
}
