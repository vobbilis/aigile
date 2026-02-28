import { useState } from 'react'
import { submitMetric } from '../api'

interface Props {
  onSubmit: () => void
}

export function MetricForm({ onSubmit }: Props) {
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !value.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await submitMetric({ name: name.trim(), value: parseFloat(value) })
      setName('')
      setValue('')
      onSubmit()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submit failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="metric-form">
      <input
        type="text"
        placeholder="metric name (e.g. cpu)"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />
      <input
        type="number"
        placeholder="value"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        step="any"
        required
      />
      <button type="submit" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit Metric'}
      </button>
      {error && <span className="error">{error}</span>}
    </form>
  )
}
