const BASE = '/api'

export type AlertOperator = 'gt' | 'lt' | 'eq'
export type AlertState = 'ok' | 'firing'

export interface AlertRule {
  id: string
  metric_name: string
  operator: AlertOperator
  threshold: number
  state: AlertState
  created_at: string
}

export interface AlertRuleIn {
  metric_name: string
  operator: AlertOperator
  threshold: number
}

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

export async function fetchAlerts(): Promise<AlertRule[]> {
  const res = await fetch(`${BASE}/alerts`)
  if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.status}`)
  return res.json()
}

export async function fetchMetricHistory(
  name: string,
  limit: number = 20,
): Promise<Metric[]> {
  const res = await fetch(`${BASE}/metrics/${name}/history?limit=${limit}`)
  if (!res.ok) throw new Error(`Failed to fetch metric history: ${res.status}`)
  return res.json()
}

export async function createAlert(rule: AlertRuleIn): Promise<AlertRule> {
  const res = await fetch(`${BASE}/alerts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
  })
  if (!res.ok || res.status !== 201)
    throw new Error(`Failed to create alert: ${res.status}`)
  return res.json()
}

export async function deleteAlert(ruleId: string): Promise<{ deleted: number }> {
  const res = await fetch(`${BASE}/alerts/${ruleId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete alert: ${res.status}`)
  return res.json()
}
