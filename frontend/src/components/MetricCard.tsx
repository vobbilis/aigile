import { deleteMetric, type Metric } from '../api'

interface Props {
  metric: Metric
  onDelete: () => void
}

export function MetricCard({ metric, onDelete }: Props) {
  const handleDelete = async () => {
    await deleteMetric(metric.name)
    onDelete()
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
