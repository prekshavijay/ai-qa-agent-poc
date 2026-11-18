export type HealthStatus = {
  status: string
  service: string
  environment: string
  version?: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function fetchHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE}/health`)
  if (!response.ok) {
    throw new Error(`Health check failed (${response.status})`)
  }
  return response.json() as Promise<HealthStatus>
}
