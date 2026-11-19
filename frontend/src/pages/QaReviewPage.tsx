import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ReviewStatusBadge } from '../components/qaReview/ReviewStatusBadge'
import { SectionCard } from '../components/ui/SectionCard'
import { formatToken } from '../components/requirements/StatusBadge'
import {
  ApiRequestError,
  approveTestCase,
  clarifyTestCase,
  fetchManagementHealth,
  fetchReviewHistory,
  fetchStoryTestCases,
  fetchVersionHistory,
  rejectTestCase,
  updateManagedTestCase,
} from '../services/testCaseManagement'
import type {
  ManagedTestCase,
  ManagedTestCaseReview,
  ManagedTestCaseVersion,
  ReviewStatus,
  StoryTestCaseSummary,
  TestCaseEditRequest,
  TestCaseManagementHealth,
} from '../types/testCaseManagement'
import type {
  AutomationSuitability,
  TestPriority,
  TestType,
} from '../types/testCases'

type PanelMode =
  | 'details'
  | 'edit'
  | 'versions'
  | 'reviews'
  | 'reject'
  | 'clarify'
  | null

const STATUS_OPTIONS: Array<ReviewStatus | 'all'> = [
  'all',
  'pending_review',
  'approved',
  'rejected',
  'needs_clarification',
]

const PRIORITY_OPTIONS: Array<TestPriority | 'all'> = [
  'all',
  'critical',
  'high',
  'medium',
  'low',
]

const TYPE_OPTIONS: Array<TestType | 'all'> = [
  'all',
  'positive',
  'negative',
  'boundary',
  'edge',
  'integration',
]

function linesToList(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function listToLines(values: string[]): string {
  return values.join('\n')
}

function emptyEditForm(testCase: ManagedTestCase): TestCaseEditRequest {
  return {
    title: testCase.title,
    objective: testCase.objective,
    test_type: testCase.test_type,
    priority: testCase.priority,
    preconditions: [...testCase.preconditions],
    test_data: [...testCase.test_data],
    steps: testCase.steps.map((step) => ({ ...step })),
    expected_result: testCase.expected_result,
    automation_suitability: testCase.automation_suitability,
    assumptions: [...testCase.assumptions],
    needs_clarification: testCase.needs_clarification,
    requirement_id: testCase.requirement_id,
    acceptance_criterion_id: testCase.acceptance_criterion_id,
    reviewer_id: '',
    comments: '',
  }
}

export function QaReviewPage() {
  const [storyId, setStoryId] = useState('')
  const [loadedStoryId, setLoadedStoryId] = useState('')
  const [summary, setSummary] = useState<StoryTestCaseSummary | null>(null)
  const [health, setHealth] = useState<TestCaseManagementHealth | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [statusFilter, setStatusFilter] = useState<ReviewStatus | 'all'>('all')
  const [priorityFilter, setPriorityFilter] = useState<TestPriority | 'all'>('all')
  const [typeFilter, setTypeFilter] = useState<TestType | 'all'>('all')

  const [selected, setSelected] = useState<ManagedTestCase | null>(null)
  const [panel, setPanel] = useState<PanelMode>(null)
  const [editForm, setEditForm] = useState<TestCaseEditRequest | null>(null)
  const [versions, setVersions] = useState<ManagedTestCaseVersion[]>([])
  const [reviews, setReviews] = useState<ManagedTestCaseReview[]>([])
  const [reviewerId, setReviewerId] = useState('')
  const [actionComments, setActionComments] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchManagementHealth()
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

  const refreshStory = useCallback(async (id: string) => {
    const trimmed = id.trim()
    if (!trimmed) {
      setError('Enter a story ID to load test cases for review.')
      return
    }
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const data = await fetchStoryTestCases(trimmed)
      setSummary(data)
      setLoadedStoryId(trimmed)
      setSelected((current) => {
        if (!current) {
          return null
        }
        return (
          data.test_cases.find(
            (item) => item.test_case_id === current.test_case_id,
          ) ?? null
        )
      })
    } catch (err) {
      const message =
        err instanceof ApiRequestError
          ? err.message
          : 'Unable to load test cases for this story.'
      setError(message)
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const filteredCases = useMemo(() => {
    if (!summary) {
      return []
    }
    return summary.test_cases.filter((item) => {
      if (statusFilter !== 'all' && item.review_status !== statusFilter) {
        return false
      }
      if (priorityFilter !== 'all' && item.priority !== priorityFilter) {
        return false
      }
      if (typeFilter !== 'all' && item.test_type !== typeFilter) {
        return false
      }
      return true
    })
  }, [summary, statusFilter, priorityFilter, typeFilter])

  function openPanel(testCase: ManagedTestCase, mode: PanelMode) {
    setSelected(testCase)
    setPanel(mode)
    setActionComments('')
    setError(null)
    setSuccess(null)
    if (mode === 'edit') {
      setEditForm(emptyEditForm(testCase))
    }
  }

  async function openHistory(testCase: ManagedTestCase, mode: 'versions' | 'reviews') {
    openPanel(testCase, mode)
    setActionBusy(true)
    try {
      if (mode === 'versions') {
        const data = await fetchVersionHistory(testCase.test_case_id, testCase.story_id)
        setVersions(data)
      } else {
        const data = await fetchReviewHistory(testCase.test_case_id, testCase.story_id)
        setReviews(data)
      }
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Unable to load history.')
      setPanel(null)
    } finally {
      setActionBusy(false)
    }
  }

  async function handleApprove(testCase: ManagedTestCase) {
    const confirmed = window.confirm(
      `Approve ${testCase.test_case_id} (version ${testCase.current_version})?`,
    )
    if (!confirmed) {
      return
    }
    setActionBusy(true)
    setError(null)
    setSuccess(null)
    try {
      await approveTestCase(
        testCase.test_case_id,
        { reviewer_id: reviewerId.trim() || null, comments: actionComments.trim() || null },
        testCase.story_id,
      )
      setSuccess(`${testCase.test_case_id} approved.`)
      setPanel(null)
      await refreshStory(testCase.story_id)
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Approval failed.')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleReject() {
    if (!selected) {
      return
    }
    if (!actionComments.trim()) {
      setError('A rejection reason is required.')
      return
    }
    const confirmed = window.confirm(`Reject ${selected.test_case_id}?`)
    if (!confirmed) {
      return
    }
    setActionBusy(true)
    setError(null)
    setSuccess(null)
    try {
      await rejectTestCase(
        selected.test_case_id,
        {
          reviewer_id: reviewerId.trim() || null,
          comments: actionComments.trim(),
        },
        selected.story_id,
      )
      setSuccess(`${selected.test_case_id} rejected.`)
      setPanel(null)
      await refreshStory(selected.story_id)
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Rejection failed.')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleClarify() {
    if (!selected) {
      return
    }
    if (!actionComments.trim()) {
      setError('Clarification comments are required.')
      return
    }
    setActionBusy(true)
    setError(null)
    setSuccess(null)
    try {
      await clarifyTestCase(
        selected.test_case_id,
        {
          reviewer_id: reviewerId.trim() || null,
          comments: actionComments.trim(),
        },
        selected.story_id,
      )
      setSuccess(`Clarification requested for ${selected.test_case_id}.`)
      setPanel(null)
      await refreshStory(selected.story_id)
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : 'Clarification request failed.',
      )
    } finally {
      setActionBusy(false)
    }
  }

  async function handleSaveEdit() {
    if (!selected || !editForm) {
      return
    }
    setActionBusy(true)
    setError(null)
    setSuccess(null)
    try {
      await updateManagedTestCase(
        selected.test_case_id,
        {
          ...editForm,
          reviewer_id: reviewerId.trim() || null,
        },
        selected.story_id,
      )
      setSuccess(`${selected.test_case_id} updated.`)
      setPanel(null)
      await refreshStory(selected.story_id)
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Update failed.')
    } finally {
      setActionBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          QA Review
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Review, edit, approve, or reject AI-generated test cases. Cases start as
          pending review and keep version history.
        </p>
        <p className="mt-3 text-sm text-slate-500">
          {health?.note ?? 'Checking test case management health…'}
        </p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[12rem] flex-1 text-sm">
            <span className="mb-1 block text-slate-600">Story ID</span>
            <input
              value={storyId}
              onChange={(event) => setStoryId(event.target.value)}
              placeholder="e.g. STORY-101"
              className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="min-w-[10rem] text-sm">
            <span className="mb-1 block text-slate-600">Reviewer ID (optional)</span>
            <input
              value={reviewerId}
              onChange={(event) => setReviewerId(event.target.value)}
              placeholder="Optional"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <button
            type="button"
            disabled={loading}
            onClick={() => refreshStory(storyId)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400"
          >
            {loading ? 'Loading…' : 'Load story'}
          </button>
        </div>
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

      {summary ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <SummaryStat label="Generated" value={summary.total} />
            <SummaryStat label="Pending review" value={summary.pending_review} />
            <SummaryStat label="Approved" value={summary.approved} />
            <SummaryStat label="Rejected" value={summary.rejected} />
            <SummaryStat
              label="Needs clarification"
              value={summary.needs_clarification}
            />
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-medium text-slate-800">
              Story <span className="font-mono">{loadedStoryId}</span>
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <FilterSelect
                label="Review status"
                value={statusFilter}
                options={STATUS_OPTIONS}
                onChange={(value) => setStatusFilter(value as ReviewStatus | 'all')}
              />
              <FilterSelect
                label="Priority"
                value={priorityFilter}
                options={PRIORITY_OPTIONS}
                onChange={(value) => setPriorityFilter(value as TestPriority | 'all')}
              />
              <FilterSelect
                label="Test type"
                value={typeFilter}
                options={TYPE_OPTIONS}
                onChange={(value) => setTypeFilter(value as TestType | 'all')}
              />
            </div>
          </section>

          <section className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Test case</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Requirement</th>
                  <th className="px-3 py-2">Criterion</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Priority</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Version</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.map((testCase) => (
                  <tr key={testCase.test_case_id} className="border-b border-slate-100">
                    <td className="px-3 py-3 font-mono text-xs text-slate-700">
                      {testCase.test_case_id}
                    </td>
                    <td className="max-w-[14rem] px-3 py-3 text-slate-800">
                      {testCase.title}
                    </td>
                    <td className="px-3 py-3 font-mono text-xs">
                      {testCase.requirement_id}
                    </td>
                    <td className="px-3 py-3 font-mono text-xs">
                      {testCase.acceptance_criterion_id ?? '—'}
                    </td>
                    <td className="px-3 py-3">{testCase.test_type}</td>
                    <td className="px-3 py-3">{testCase.priority}</td>
                    <td className="px-3 py-3">
                      <ReviewStatusBadge status={testCase.review_status} />
                    </td>
                    <td className="px-3 py-3">v{testCase.current_version}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1">
                        <ActionButton
                          label="View"
                          onClick={() => openPanel(testCase, 'details')}
                        />
                        <ActionButton
                          label="Edit"
                          onClick={() => openPanel(testCase, 'edit')}
                        />
                        <ActionButton
                          label="Approve"
                          disabled={
                            actionBusy ||
                            testCase.review_status !== 'pending_review'
                          }
                          onClick={() => handleApprove(testCase)}
                        />
                        <ActionButton
                          label="Reject"
                          disabled={
                            actionBusy || testCase.review_status === 'approved'
                          }
                          onClick={() => openPanel(testCase, 'reject')}
                        />
                        <ActionButton
                          label="Clarify"
                          disabled={
                            actionBusy || testCase.review_status === 'approved'
                          }
                          onClick={() => openPanel(testCase, 'clarify')}
                        />
                        <ActionButton
                          label="Versions"
                          onClick={() => openHistory(testCase, 'versions')}
                        />
                        <ActionButton
                          label="Reviews"
                          onClick={() => openHistory(testCase, 'reviews')}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredCases.length === 0 ? (
                  <tr>
                    <td
                      colSpan={9}
                      className="px-3 py-6 text-center text-sm text-slate-500"
                    >
                      No test cases match the current filters.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>
        </>
      ) : (
        <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-6 text-sm text-slate-500">
          Load a story ID after generating test cases to begin QA review.
        </p>
      )}

      {selected && panel === 'details' ? (
        <DetailPanel
          testCase={selected}
          onClose={() => setPanel(null)}
        />
      ) : null}

      {selected && panel === 'edit' && editForm ? (
        <EditPanel
          testCase={selected}
          form={editForm}
          busy={actionBusy}
          onChange={setEditForm}
          onCancel={() => setPanel(null)}
          onSave={handleSaveEdit}
        />
      ) : null}

      {selected && panel === 'reject' ? (
        <CommentActionPanel
          title={`Reject ${selected.test_case_id}`}
          submitLabel="Confirm reject"
          comments={actionComments}
          busy={actionBusy}
          onCommentsChange={setActionComments}
          onCancel={() => setPanel(null)}
          onSubmit={handleReject}
        />
      ) : null}

      {selected && panel === 'clarify' ? (
        <CommentActionPanel
          title={`Request clarification for ${selected.test_case_id}`}
          submitLabel="Submit clarification request"
          comments={actionComments}
          busy={actionBusy}
          onCommentsChange={setActionComments}
          onCancel={() => setPanel(null)}
          onSubmit={handleClarify}
        />
      ) : null}

      {selected && panel === 'versions' ? (
        <HistoryPanel
          title={`Version history · ${selected.test_case_id}`}
          onClose={() => setPanel(null)}
        >
          {versions.map((version) => (
            <div
              key={version.version_number}
              className="rounded-md border border-slate-200 p-3 text-sm"
            >
              <p className="font-medium text-slate-800">
                Version {version.version_number}
                {version.is_original ? ' · original' : ''}
                {version.is_approved_snapshot ? ' · approved snapshot' : ''}
              </p>
              <p className="mt-1 text-slate-600">{version.title}</p>
              <p className="mt-1 text-xs text-slate-500">
                {version.test_type} · {version.priority} ·{' '}
                {formatToken(version.automation_suitability)}
              </p>
            </div>
          ))}
        </HistoryPanel>
      ) : null}

      {selected && panel === 'reviews' ? (
        <HistoryPanel
          title={`Review history · ${selected.test_case_id}`}
          onClose={() => setPanel(null)}
        >
          {reviews.map((review, index) => (
            <div
              key={`${review.review_action}-${review.created_at}-${index}`}
              className="rounded-md border border-slate-200 p-3 text-sm"
            >
              <p className="font-medium text-slate-800">
                {formatToken(review.review_action)} · v{review.version_number}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {review.reviewer_id ? `Reviewer: ${review.reviewer_id}` : 'No reviewer ID'}{' '}
                · {new Date(review.created_at).toLocaleString()}
              </p>
              {review.comments ? (
                <p className="mt-2 text-slate-600">{review.comments}</p>
              ) : null}
            </div>
          ))}
        </HistoryPanel>
      ) : null}
    </main>
  )
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-slate-600">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === 'all' ? 'All' : formatToken(option)}
          </option>
        ))}
      </select>
    </label>
  )
}

function ActionButton({
  label,
  onClick,
  disabled,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {label}
    </button>
  )
}

function DetailPanel({
  testCase,
  onClose,
}: {
  testCase: ManagedTestCase
  onClose: () => void
}) {
  return (
    <SectionCard
      title={`${testCase.test_case_id} · details`}
      action={
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-slate-600 hover:text-slate-900"
        >
          Close
        </button>
      }
    >
      <div className="space-y-3 text-sm text-slate-700">
        <p>
          <span className="font-medium">Title:</span> {testCase.title}
        </p>
        <p>
          <span className="font-medium">Objective:</span> {testCase.objective}
        </p>
        <p>
          <span className="font-medium">Expected result:</span>{' '}
          {testCase.expected_result}
        </p>
        <div>
          <p className="font-medium">Preconditions</p>
          <ul className="mt-1 list-disc pl-5">
            {testCase.preconditions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-medium">Steps</p>
          <ol className="mt-1 list-decimal pl-5">
            {testCase.steps.map((step) => (
              <li key={step.step_number} className="mb-2">
                <p>{step.action}</p>
                <p className="text-slate-500">Expected: {step.expected_result}</p>
              </li>
            ))}
          </ol>
        </div>
        {testCase.original_version ? (
          <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-3">
            <p className="font-medium text-slate-800">Original generated content</p>
            <p className="mt-1">{testCase.original_version.title}</p>
            <p className="mt-1 text-slate-600">{testCase.original_version.objective}</p>
          </div>
        ) : null}
      </div>
    </SectionCard>
  )
}

function EditPanel({
  testCase,
  form,
  busy,
  onChange,
  onCancel,
  onSave,
}: {
  testCase: ManagedTestCase
  form: TestCaseEditRequest
  busy: boolean
  onChange: (form: TestCaseEditRequest) => void
  onCancel: () => void
  onSave: () => void
}) {
  return (
    <SectionCard
      title={`Edit ${testCase.test_case_id}`}
      action={
        <button
          type="button"
          onClick={onCancel}
          className="text-sm text-slate-600 hover:text-slate-900"
        >
          Cancel
        </button>
      }
    >
      <div className="grid gap-3">
        <TextField
          label="Title"
          value={form.title}
          onChange={(title) => onChange({ ...form, title })}
        />
        <TextAreaField
          label="Objective"
          value={form.objective}
          onChange={(objective) => onChange({ ...form, objective })}
        />
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label="Test type"
            value={form.test_type}
            options={TYPE_OPTIONS.filter((item) => item !== 'all') as TestType[]}
            onChange={(test_type) =>
              onChange({ ...form, test_type: test_type as TestType })
            }
          />
          <SelectField
            label="Priority"
            value={form.priority}
            options={PRIORITY_OPTIONS.filter((item) => item !== 'all') as TestPriority[]}
            onChange={(priority) =>
              onChange({ ...form, priority: priority as TestPriority })
            }
          />
          <SelectField
            label="Automation suitability"
            value={form.automation_suitability}
            options={[
              'suitable',
              'partially_suitable',
              'manual_only',
            ] as AutomationSuitability[]}
            onChange={(automation_suitability) =>
              onChange({
                ...form,
                automation_suitability:
                  automation_suitability as AutomationSuitability,
              })
            }
          />
        </div>
        <TextAreaField
          label="Preconditions (one per line)"
          value={listToLines(form.preconditions)}
          onChange={(value) =>
            onChange({ ...form, preconditions: linesToList(value) })
          }
        />
        <TextAreaField
          label="Test data (one per line)"
          value={listToLines(form.test_data)}
          onChange={(value) => onChange({ ...form, test_data: linesToList(value) })}
        />
        <TextAreaField
          label="Expected result"
          value={form.expected_result}
          onChange={(expected_result) => onChange({ ...form, expected_result })}
        />
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-700">Steps</p>
          {form.steps.map((step, index) => (
            <div
              key={step.step_number}
              className="grid gap-2 rounded-md border border-slate-200 p-3"
            >
              <TextAreaField
                label={`Step ${index + 1} action`}
                value={step.action}
                onChange={(action) => {
                  const steps = form.steps.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, action } : item,
                  )
                  onChange({ ...form, steps })
                }}
              />
              <TextAreaField
                label={`Step ${index + 1} expected result`}
                value={step.expected_result}
                onChange={(expected_result) => {
                  const steps = form.steps.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, expected_result } : item,
                  )
                  onChange({ ...form, steps })
                }}
              />
            </div>
          ))}
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={onSave}
          className="justify-self-start rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400"
        >
          {busy ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </SectionCard>
  )
}

function CommentActionPanel({
  title,
  submitLabel,
  comments,
  busy,
  onCommentsChange,
  onCancel,
  onSubmit,
}: {
  title: string
  submitLabel: string
  comments: string
  busy: boolean
  onCommentsChange: (value: string) => void
  onCancel: () => void
  onSubmit: () => void
}) {
  return (
    <SectionCard
      title={title}
      action={
        <button
          type="button"
          onClick={onCancel}
          className="text-sm text-slate-600 hover:text-slate-900"
        >
          Cancel
        </button>
      }
    >
      <TextAreaField
        label="Reviewer comments (required)"
        value={comments}
        onChange={onCommentsChange}
      />
      <button
        type="button"
        disabled={busy}
        onClick={onSubmit}
        className="mt-3 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400"
      >
        {busy ? 'Submitting…' : submitLabel}
      </button>
    </SectionCard>
  )
}

function HistoryPanel({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  return (
    <SectionCard
      title={title}
      action={
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-slate-600 hover:text-slate-900"
        >
          Close
        </button>
      }
    >
      <div className="space-y-3">{children}</div>
    </SectionCard>
  )
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-600">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      />
    </label>
  )
}

function TextAreaField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-600">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      />
    </label>
  )
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-600">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {formatToken(option)}
          </option>
        ))}
      </select>
    </label>
  )
}
