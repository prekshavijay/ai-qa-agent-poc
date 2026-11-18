import { useEffect, useState } from 'react'
import { fetchHealth, type HealthStatus } from '../services/api'

export function HomePage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    fetchHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data)
          setError(null)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth(null)
          setError('Backend unreachable — start the API on port 8000')
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main>
      <div className="mx-auto flex min-h-[calc(100vh-4.5rem)] max-w-3xl flex-col items-center justify-center px-6 py-16 text-center">
        <p className="mb-3 text-sm font-medium uppercase tracking-[0.2em] text-slate-500">
          Proof of Concept
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
          AI QA Agent POC
        </h1>
        <p className="mt-4 max-w-xl text-base text-slate-600 sm:text-lg">
          Foundation stage — scaffolding for an AI-assisted software QA lifecycle.
        </p>

        <div className="mt-10 rounded-lg border border-slate-200 bg-white px-5 py-4 text-left text-sm shadow-sm">
          <p className="font-medium text-slate-800">API health</p>
          {health ? (
            <p className="mt-1 text-emerald-700">
              {health.status} · {health.service} · {health.environment}
            </p>
          ) : (
            <p className="mt-1 text-amber-700">{error ?? 'Checking…'}</p>
          )}
        </div>
      </div>
    </main>
  )
}
