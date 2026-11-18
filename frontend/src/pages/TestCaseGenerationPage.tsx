import { useEffect, useState } from 'react'
import { StoryForm } from '../components/requirements/StoryForm'
import { AnalysisResults } from '../components/requirements/AnalysisResults'
import { TestCaseResults } from '../components/testCases/TestCaseResults'
import { useTestCaseGeneration } from '../hooks/useTestCaseGeneration'
import {
  clearStoredAnalysis,
  readStoredAnalysis,
} from '../services/analysisHandoff'
import { fetchTestCaseHealth } from '../services/testCases'
import type { TestCaseGenerationHealth } from '../types/testCases'

export function TestCaseGenerationPage() {

  const {
    analysis,
    result,
    error,
    analyzing,
    generating,
    analyze,
    generate,
    loadAnalysis,
  } = useTestCaseGeneration()
  const [health, setHealth] = useState<TestCaseGenerationHealth | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [importedNote, setImportedNote] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchTestCaseHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data)
          setHealthError(null)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth(null)
          setHealthError('Test case generation health is unavailable.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const stored = readStoredAnalysis()
    if (!stored) {
      return
    }
    loadAnalysis(stored)
    setImportedNote(
      `Loaded requirement analysis for ${stored.story_id} from the Requirement Analysis page.`,
    )
    clearStoredAnalysis()
    // Load once on mount from Requirement Analysis handoff.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])


  const busy = analyzing || generating

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-6 py-8 lg:grid-cols-2">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Test Case Generation
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Analyze a user story, then generate traceable test cases from that structured
          analysis. Requirements are not re-entered or re-invented.
        </p>
        <p className="mt-3 text-sm text-slate-500">
          {health ? health.note : (healthError ?? 'Checking the test case generation service…')}
        </p>

        {importedNote ? (
          <p className="mt-3 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
            {importedNote}
          </p>
        ) : null}

        <div className="mt-6">
          <StoryForm loading={busy} onSubmit={analyze} />
        </div>

        {analysis ? (
          <div className="mt-6 space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Ready analysis
              </p>
              <p className="font-mono text-sm text-slate-800">{analysis.story_id}</p>
              <p className="mt-1 text-sm text-slate-600">
                {analysis.functional_requirements.length} functional ·{' '}
                {analysis.non_functional_requirements.length} non-functional ·{' '}
                {analysis.acceptance_criteria.length} acceptance criteria
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => generate(analysis)}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {generating ? 'Generating test cases…' : 'Generate Test Cases'}
            </button>
          </div>
        ) : null}
      </section>

      <section aria-live="polite" className="space-y-4">
        {analyzing ? (
          <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
            <span
              className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-800"
              aria-hidden="true"
            />
            <span role="status">Analyzing requirements…</span>
          </div>
        ) : null}

        {generating ? (
          <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
            <span
              className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-800"
              aria-hidden="true"
            />
            <span role="status">Generating test cases…</span>
          </div>
        ) : null}

        {error ? (
          <p
            role="alert"
            className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
          >
            {error}
          </p>
        ) : null}

        {result ? <TestCaseResults generation={result} /> : null}

        {!result && analysis && !generating ? (
          <div className="space-y-3">
            <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-3 text-sm text-slate-500">
              Requirement analysis is ready. Generate test cases to view scenarios here.
            </p>
            <AnalysisResults analysis={analysis} />
          </div>
        ) : null}

        {!busy && !error && !result && !analysis ? (
          <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-6 text-sm text-slate-500">
            Submit a story to analyze requirements, or open this page from Requirement
            Analysis after a successful run.
          </p>
        ) : null}
      </section>
    </main>
  )
}
