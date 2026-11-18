import { useEffect, useState } from 'react'
import { AnalysisResults } from '../components/requirements/AnalysisResults'
import { StoryForm } from '../components/requirements/StoryForm'
import { useRequirementAnalysis } from '../hooks/useRequirementAnalysis'
import { storeAnalysis } from '../services/analysisHandoff'
import { fetchRequirementHealth } from '../services/requirements'
import type { RequirementAnalysisHealth } from '../types/requirements'

type RequirementAnalysisPageProps = {
  onNavigateToTestCases?: () => void
}

export function RequirementAnalysisPage({
  onNavigateToTestCases,
}: RequirementAnalysisPageProps) {
  const { result, error, loading, analyze } = useRequirementAnalysis()
  const [health, setHealth] = useState<RequirementAnalysisHealth | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)


  useEffect(() => {
    let cancelled = false
    fetchRequirementHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data)
          setHealthError(null)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth(null)
          setHealthError('Requirement service health is unavailable.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-6 py-8 lg:grid-cols-2">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Requirement Analysis
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Turn a user story into structured, testable requirements. The analyzer keeps only
          statements that are written in the story.
        </p>
        <p className="mt-3 text-sm text-slate-500">
          {health
            ? health.note
            : (healthError ?? 'Checking the requirement analysis service…')}
        </p>
        <div className="mt-6">
          <StoryForm loading={loading} onSubmit={analyze} />
        </div>
      </section>

      <section aria-live="polite">
        {loading ? (
          <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
            <span
              className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-800"
              aria-hidden="true"
            />
            <span role="status">Analyzing requirements…</span>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {error}
          </p>
        ) : null}

        {result ? (
          <AnalysisResults
            analysis={result}
            onGenerateTestCases={
              onNavigateToTestCases
                ? () => {
                    storeAnalysis(result)
                    onNavigateToTestCases()
                  }
                : undefined
            }
          />
        ) : null}

        {!loading && !error && !result ? (
          <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-6 text-sm text-slate-500">
            Analysis results appear here after you submit a story.
          </p>
        ) : null}
      </section>
    </main>
  )
}
