import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ResultStatusBadge,
  RunStatusBadge,
} from '../components/qaExecution/ExecutionStatusBadge'
import { SectionCard } from '../components/ui/SectionCard'
import { fetchApprovedTestCases } from '../services/testCaseManagement'
import {
  ApiRequestError,
  createExecutionRun,
  fetchExecutionHealth,
  fetchExecutionRun,
  fetchExecutionRuns,
  recordExecutionResult,
} from '../services/qaExecution'
import type { ManagedTestCase } from '../types/testCaseManagement'
import type {
  ExecutionResult,
  ExecutionResultStatus,
  ExecutionRun,
  ExecutionRunDetail,
  QaExecutionHealth,
} from '../types/qaExecution'

const RESULT_OPTIONS: ExecutionResultStatus[] = [
  'passed',
  'failed',
  'blocked',
  'not_run',
]

type ResultDraft = {
  status: ExecutionResultStatus
  actual_result: string
  error_details: string
  evidence: string
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiRequestError || err instanceof Error) {
    return err.message
  }
  return fallback
}

function formatWhen(value: string | null): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) {
    return '—'
  }
  if (seconds < 60) {
    return `${Number(seconds.toFixed(1))}s`
  }
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.round(seconds % 60)
  return `${minutes}m ${remainder}s`
}

function countSummary(run: Pick<
  ExecutionRun,
  'passed_count' | 'failed_count' | 'blocked_count' | 'not_run_count'
>): string {
  return `${run.passed_count} passed · ${run.failed_count} failed · ${run.blocked_count} blocked · ${run.not_run_count} not run`
}

function draftFromResult(result: ExecutionResult): ResultDraft {
  const hasEvidence = result.evidence && Object.keys(result.evidence).length > 0
  return {
    status: result.status,
    actual_result: result.actual_result ?? '',
    error_details: result.error_details ?? '',
    evidence: hasEvidence ? JSON.stringify(result.evidence, null, 2) : '',
  }
}

function parseEvidence(raw: string): Record<string, unknown> {
  const trimmed = raw.trim()
  if (!trimmed) {
    return {}
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(trimmed)
  } catch {
    throw new Error('Evidence must be valid JSON, for example {"note": "manual"}.')
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('Evidence must be a JSON object, for example {"note": "manual"}.')
  }
  return parsed as Record<string, unknown>
}

export function QaExecutionPage() {
  const [health, setHealth] = useState<QaExecutionHealth | null>(null)
  const [filterStoryId, setFilterStoryId] = useState('')
  const [runs, setRuns] = useState<ExecutionRun[]>([])
  const [listLoading, setListLoading] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ExecutionRunDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const [createStoryId, setCreateStoryId] = useState('')
  const [loadedStoryId, setLoadedStoryId] = useState('')
  const [approvedCases, setApprovedCases] = useState<ManagedTestCase[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [approvedLoading, setApprovedLoading] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)

  const [selectedResultId, setSelectedResultId] = useState<number | null>(null)
  const [draft, setDraft] = useState<ResultDraft>({
    status: 'not_run',
    actual_result: '',
    error_details: '',
    evidence: '',
  })
  const [recordBusy, setRecordBusy] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadRuns = useCallback(async (storyId?: string) => {
    setListLoading(true)
    try {
      const data = await fetchExecutionRuns(storyId)
      setRuns(data.runs)
      setSelectedRunId((current) => {
        if (current && data.runs.some((run) => run.run_id === current)) {
          return current
        }
        return data.runs[0]?.run_id ?? null
      })
    } catch (err) {
      setError(errorMessage(err, 'Unable to load execution runs.'))
      setRuns([])
    } finally {
      setListLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (runId: string) => {
    setDetailLoading(true)
    try {
      const data = await fetchExecutionRun(runId)
      setDetail(data)
      setRuns((current) =>
        current.map((run) => (run.run_id === data.run_id ? { ...run, ...data } : run)),
      )
    } catch (err) {
      setError(errorMessage(err, 'Unable to load this execution run.'))
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchExecutionHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void loadRuns()
  }, [loadRuns])

  useEffect(() => {
    if (!selectedRunId) {
      setDetail(null)
      return
    }
    void loadDetail(selectedRunId)
  }, [selectedRunId, loadDetail])

  useEffect(() => {
    if (!detail?.results.length) {
      setSelectedResultId(null)
      return
    }
    setSelectedResultId((current) => {
      if (current && detail.results.some((item) => item.id === current)) {
        return current
      }
      return detail.results[0].id
    })
  }, [detail])

  const selectedResult = useMemo(
    () => detail?.results.find((item) => item.id === selectedResultId) ?? null,
    [detail, selectedResultId],
  )

  useEffect(() => {
    if (selectedResult) {
      setDraft(draftFromResult(selectedResult))
    }
  }, [selectedResult])

  const storyReady = createStoryId.trim() !== '' && createStoryId.trim() === loadedStoryId
  const allSelected =
    approvedCases.length > 0 && selectedCaseIds.length === approvedCases.length

  async function handleLoadApproved() {
    const storyId = createStoryId.trim()
    if (!storyId) {
      setError('Enter a story ID to load approved test cases.')
      return
    }
    setApprovedLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const cases = await fetchApprovedTestCases(storyId)
      setApprovedCases(cases)
      setLoadedStoryId(storyId)
      setSelectedCaseIds(cases.map((item) => item.test_case_id))
      if (cases.length === 0) {
        setError(
          'No approved test cases for this story. Approve cases in QA Review before creating a run.',
        )
      }
    } catch (err) {
      setApprovedCases([])
      setLoadedStoryId('')
      setSelectedCaseIds([])
      setError(errorMessage(err, 'Unable to load approved test cases.'))
    } finally {
      setApprovedLoading(false)
    }
  }

  function toggleCase(testCaseId: string) {
    setSelectedCaseIds((current) =>
      current.includes(testCaseId)
        ? current.filter((id) => id !== testCaseId)
        : [...current, testCaseId],
    )
  }

  async function handleCreateRun() {
    const storyId = createStoryId.trim()
    if (!storyReady) {
      setError('Load approved test cases for this story ID before creating a run.')
      return
    }
    if (selectedCaseIds.length === 0) {
      setError('Select at least one approved test case.')
      return
    }
    setCreateBusy(true)
    setError(null)
    setSuccess(null)
    try {
      const created = await createExecutionRun({
        story_id: storyId,
        test_case_ids: selectedCaseIds,
        trigger_source: 'manual',
      })
      setSuccess(
        `Created ${created.run_id} with ${created.total_test_cases} test cases. Nothing was executed.`,
      )
      setFilterStoryId(storyId)
      setSelectedRunId(created.run_id)
      setDetail(created)
      await loadRuns(storyId)
    } catch (err) {
      setError(errorMessage(err, 'Unable to create the execution run.'))
    } finally {
      setCreateBusy(false)
    }
  }

  async function handleRecordResult() {
    if (!detail || !selectedResult) {
      return
    }
    let evidence: Record<string, unknown>
    try {
      evidence = parseEvidence(draft.evidence)
    } catch (err) {
      setError(errorMessage(err, 'Evidence must be a JSON object.'))
      setSuccess(null)
      return
    }
    setRecordBusy(true)
    setError(null)
    setSuccess(null)
    try {
      const updated = await recordExecutionResult(detail.run_id, {
        test_case_id: selectedResult.test_case_id,
        status: draft.status,
        actual_result: draft.actual_result,
        error_details: draft.error_details,
        evidence,
      })
      setDetail(updated)
      setRuns((current) =>
        current.map((run) =>
          run.run_id === updated.run_id ? { ...run, ...updated } : run,
        ),
      )
      setSuccess(
        `Recorded ${draft.status.replace('_', ' ')} for ${selectedResult.test_case_id}. No test was executed.`,
      )
    } catch (err) {
      setError(errorMessage(err, 'Unable to record this result.'))
    } finally {
      setRecordBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          QA Execution
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Create an execution run from QA-approved test cases and record results
          manually. Rejected, pending-review, and needs-clarification cases are
          not included.
        </p>
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Automated execution is not implemented yet. Creating a run does not
          launch a browser or API test, and recording a result only stores what
          you enter.
        </p>
        <p className="mt-3 text-sm text-slate-500">
          {health?.note ?? 'Checking QA execution health…'}
        </p>
      </section>

      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
        >
          {error}
        </p>
      ) : null}
      {success ? (
        <p
          role="status"
          className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
        >
          {success}
        </p>
      ) : null}

      <SectionCard title="Create run">
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[14rem] flex-1 text-sm">
            <span className="mb-1 block text-slate-600">Story ID for new run</span>
            <input
              value={createStoryId}
              onChange={(event) => setCreateStoryId(event.target.value)}
              placeholder="e.g. STORY-101"
              className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
            />
          </label>
          <button
            type="button"
            disabled={approvedLoading}
            onClick={() => void handleLoadApproved()}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:text-slate-400"
          >
            {approvedLoading ? 'Loading…' : 'Load approved test cases'}
          </button>
          <button
            type="button"
            disabled={createBusy || !storyReady || selectedCaseIds.length === 0}
            onClick={() => void handleCreateRun()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400"
          >
            {createBusy ? 'Creating…' : 'Create execution run'}
          </button>
        </div>

        {loadedStoryId ? (
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-sm text-slate-600">
                {approvedCases.length} approved for{' '}
                <span className="font-mono">{loadedStoryId}</span>. {selectedCaseIds.length}{' '}
                selected.
              </p>
              {approvedCases.length > 0 ? (
                <button
                  type="button"
                  onClick={() =>
                    setSelectedCaseIds(
                      allSelected
                        ? []
                        : approvedCases.map((item) => item.test_case_id),
                    )
                  }
                  className="text-sm text-slate-700 underline-offset-2 hover:underline"
                >
                  {allSelected ? 'Clear selection' : 'Select all'}
                </button>
              ) : null}
            </div>
            {approvedCases.length > 0 ? (
              <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
                {approvedCases.map((testCase) => {
                  const checked = selectedCaseIds.includes(testCase.test_case_id)
                  return (
                    <li key={testCase.test_case_id} className="px-3 py-2">
                      <label className="flex cursor-pointer items-start gap-3 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={checked}
                          onChange={() => toggleCase(testCase.test_case_id)}
                        />
                        <span>
                          <span className="font-mono text-slate-800">
                            {testCase.test_case_id}
                          </span>
                          <span className="mt-0.5 block text-slate-700">
                            {testCase.title}
                          </span>
                          <span className="mt-0.5 block text-xs text-slate-500">
                            Approved version {testCase.current_version}
                          </span>
                        </span>
                      </label>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">
                This story has no approved test cases to add.
              </p>
            )}
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            Load a story to choose the approved test cases for the run.
          </p>
        )}
      </SectionCard>

      <SectionCard
        title="Execution runs"
        action={
          <button
            type="button"
            disabled={listLoading}
            onClick={() => void loadRuns(filterStoryId)}
            className="text-sm text-slate-700 underline-offset-2 hover:underline disabled:text-slate-400"
          >
            {listLoading ? 'Refreshing…' : 'Refresh'}
          </button>
        }
      >
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <label className="min-w-[14rem] flex-1 text-sm">
            <span className="mb-1 block text-slate-600">Filter by story ID</span>
            <input
              value={filterStoryId}
              onChange={(event) => setFilterStoryId(event.target.value)}
              placeholder="Leave empty to list every run"
              className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
            />
          </label>
          <button
            type="button"
            disabled={listLoading}
            onClick={() => void loadRuns(filterStoryId)}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:text-slate-400"
          >
            Apply filter
          </button>
        </div>

        {runs.length === 0 ? (
          <p className="text-sm text-slate-500">
            {listLoading ? 'Loading runs…' : 'No execution runs yet.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-2 py-2 font-medium">Run</th>
                  <th className="px-2 py-2 font-medium">Story</th>
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">Created</th>
                  <th className="px-2 py-2 font-medium">Results</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => {
                  const selected = run.run_id === selectedRunId
                  return (
                    <tr
                      key={run.run_id}
                      className={selected ? 'bg-slate-50' : undefined}
                    >
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          onClick={() => setSelectedRunId(run.run_id)}
                          className="font-mono text-slate-900 underline-offset-2 hover:underline"
                          aria-current={selected ? 'true' : undefined}
                        >
                          {run.run_id}
                        </button>
                      </td>
                      <td className="px-2 py-2 font-mono text-slate-700">{run.story_id}</td>
                      <td className="px-2 py-2">
                        <RunStatusBadge status={run.status} />
                      </td>
                      <td className="px-2 py-2 text-slate-600">
                        {formatWhen(run.created_at)}
                      </td>
                      <td className="px-2 py-2 text-slate-600">{countSummary(run)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Run detail">
        {!selectedRunId ? (
          <p className="text-sm text-slate-500">Select a run to see its test cases.</p>
        ) : detailLoading && !detail ? (
          <p className="text-sm text-slate-500">Loading run…</p>
        ) : detail ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <p className="font-mono text-sm text-slate-900">{detail.run_id}</p>
              <RunStatusBadge status={detail.status} />
              <p className="text-sm text-slate-600">{countSummary(detail)}</p>
            </div>
            <p className="text-sm text-slate-500">
              Story <span className="font-mono">{detail.story_id}</span> · trigger{' '}
              {detail.trigger_source} · started {formatWhen(detail.started_at)} ·
              completed {formatWhen(detail.completed_at)}
            </p>
            <p className="text-sm text-slate-500">
              Each row keeps the approved version from when the run was created.
              Recording a result does not execute that test.
            </p>

            <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
              {detail.results.map((result) => {
                const selected = result.id === selectedResultId
                return (
                  <li key={result.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedResultId(result.id)}
                      className={`flex w-full flex-wrap items-start justify-between gap-3 px-3 py-3 text-left ${
                        selected ? 'bg-slate-50' : 'hover:bg-slate-50'
                      }`}
                      aria-pressed={selected}
                    >
                      <span>
                        <span className="font-mono text-sm text-slate-800">
                          {result.test_case_id}
                        </span>
                        <span className="mt-0.5 block text-sm text-slate-700">
                          {result.title}
                        </span>
                        <span className="mt-0.5 block text-xs text-slate-500">
                          Approved version {result.approved_version_number} · id{' '}
                          {result.approved_version_id}
                        </span>
                      </span>
                      <ResultStatusBadge status={result.status} />
                    </button>
                  </li>
                )
              })}
            </ul>

            {selectedResult ? (
              <form
                className="space-y-3 rounded-md border border-slate-200 p-4"
                onSubmit={(event) => {
                  event.preventDefault()
                  void handleRecordResult()
                }}
              >
                <div>
                  <h3 className="text-sm font-medium text-slate-900">
                    Record result for {selectedResult.test_case_id}
                  </h3>
                  <p className="mt-1 text-sm text-slate-600">
                    Expected: {selectedResult.expected_result}
                  </p>
                </div>
                <label className="block text-sm">
                  <span className="mb-1 block text-slate-600">Status</span>
                  <select
                    value={draft.status}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        status: event.target.value as ExecutionResultStatus,
                      }))
                    }
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  >
                    {RESULT_OPTIONS.map((status) => (
                      <option key={status} value={status}>
                        {status.replace('_', ' ')}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-slate-600">Actual result</span>
                  <textarea
                    value={draft.actual_result}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        actual_result: event.target.value,
                      }))
                    }
                    rows={3}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-slate-600">Error or failure details</span>
                  <textarea
                    value={draft.error_details}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        error_details: event.target.value,
                      }))
                    }
                    rows={2}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-slate-600">Evidence metadata (JSON)</span>
                  <textarea
                    value={draft.evidence}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        evidence: event.target.value,
                      }))
                    }
                    rows={3}
                    placeholder='{"note": "manual"}'
                    className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
                  />
                </label>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">
                    Duration {formatDuration(selectedResult.duration_seconds)} · started{' '}
                    {formatWhen(selectedResult.started_at)} · completed{' '}
                    {formatWhen(selectedResult.completed_at)}
                  </p>
                  <button
                    type="submit"
                    disabled={recordBusy}
                    className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400"
                  >
                    {recordBusy ? 'Saving…' : 'Record result'}
                  </button>
                </div>
              </form>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-slate-500">This run could not be loaded.</p>
        )}
      </SectionCard>
    </main>
  )
}
