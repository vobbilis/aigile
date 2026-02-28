const BASE = '/api'

export interface Metric {
  id: string
  name: string
  value: number
  tags: Record<string, string>
  timestamp: string
}

export interface MetricIn {
  name: string
  value: number
  tags?: Record<string, string>
}

export async function fetchMetrics(): Promise<Metric[]> {
  const res = await fetch(`${BASE}/metrics`)
  if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.status}`)
  return res.json()
}

export async function submitMetric(metric: MetricIn): Promise<Metric> {
  const res = await fetch(`${BASE}/metrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(metric),
  })
  if (!res.ok) throw new Error(`Failed to submit metric: ${res.status}`)
  return res.json()
}

export async function deleteMetric(name: string): Promise<{ deleted: number }> {
  const res = await fetch(`${BASE}/metrics/${name}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete metric: ${res.status}`)
  return res.json()
}
