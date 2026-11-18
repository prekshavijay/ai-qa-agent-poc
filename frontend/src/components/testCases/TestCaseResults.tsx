import { useMemo, useState } from 'react'
import { SectionCard } from '../ui/SectionCard'
import { formatToken } from '../requirements/StatusBadge'
import {
  TestCaseFilters,
  type TestCaseFilterState,
} from './TestCaseFilters'
import type {
  GenerationStatus,
  TestCase,
  TestCaseGenerationResponse,
} from '../../types/testCases'

type TestCaseResultsProps = {
  generation: TestCaseGenerationResponse
}

const STATUS_LABEL: Record<GenerationStatus, string> = {
  complete: 'Complete',
  partial: 'Partial',
  needs_clarification: 'Needs clarification',
  no_test_cases: 'No test cases',
}

const STATUS_CLASS: Record<GenerationStatus, string> = {
  complete: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  partial: 'bg-sky-50 text-sky-800 ring-sky-200',
  needs_clarification: 'bg-amber-50 text-amber-800 ring-amber-200',
  no_test_cases: 'bg-rose-50 text-rose-800 ring-rose-200',
}

function GenerationStatusBadge({ status }: { status: GenerationStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${STATUS_CLASS[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}

function TestCaseCard({ testCase }: { testCase: TestCase }) {
  const [open, setOpen] = useState(false)

  return (
    <li className="rounded-md border border-slate-200 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="font-mono text-slate-700">{testCase.test_case_id}</span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5">{testCase.test_type}</span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5">{testCase.priority}</span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5">
              {formatToken(testCase.automation_suitability)}
            </span>
            {testCase.needs_clarification ? (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">
                needs clarification
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-sm font-medium text-slate-900">{testCase.title}</p>
          <p className="mt-1 text-sm text-slate-600">{testCase.objective}</p>
          <p className="mt-2 text-xs text-slate-500">
            Requirement <span className="font-mono">{testCase.requirement_id}</span>
            {testCase.acceptance_criterion_id ? (
              <>
                {' '}
                · Criterion{' '}
                <span className="font-mono">{testCase.acceptance_criterion_id}</span>
              </>
            ) : null}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          aria-expanded={open}
        >
          {open ? 'Collapse' : 'Expand'}
        </button>
      </div>

      {open ? (
        <div className="mt-4 space-y-4 border-t border-slate-100 pt-4 text-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Preconditions
            </p>
            {testCase.preconditions.length === 0 ? (
              <p className="mt-1 text-slate-500">None listed.</p>
            ) : (
              <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-800">
                {testCase.preconditions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Test data
            </p>
            {testCase.test_data.length === 0 ? (
              <p className="mt-1 text-slate-500">None listed.</p>
            ) : (
              <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-800">
                {testCase.test_data.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Steps
            </p>
            <ol className="mt-2 space-y-3">
              {testCase.steps.map((step) => (
                <li key={step.step_number} className="rounded-md bg-slate-50 p-3">
                  <p className="font-medium text-slate-800">
                    Step {step.step_number}: {step.action}
                  </p>
                  <p className="mt-1 text-slate-600">
                    Expected: {step.expected_result}
                  </p>
                </li>
              ))}
            </ol>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Expected result
            </p>
            <p className="mt-1 text-slate-800">{testCase.expected_result}</p>
          </div>

          {testCase.assumptions.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Assumptions
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-800">
                {testCase.assumptions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  )
}

export function TestCaseResults({ generation }: TestCaseResultsProps) {
  const [filters, setFilters] = useState<TestCaseFilterState>({
    testType: 'all',
    priority: 'all',
    clarificationOnly: false,
  })

  const filtered = useMemo(() => {
    return generation.test_cases.filter((item) => {
      if (filters.testType !== 'all' && item.test_type !== filters.testType) {
        return false
      }
      if (filters.priority !== 'all' && item.priority !== filters.priority) {
        return false
      }
      if (filters.clarificationOnly && !item.needs_clarification) {
        return false
      }
      return true
    })
  }, [filters, generation.test_cases])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Story</p>
          <p className="font-mono text-sm text-slate-800">{generation.story_id}</p>
        </div>
        <GenerationStatusBadge status={generation.generation_status} />
      </div>

      <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
        {generation.provider_note}
      </p>

      <SectionCard title="Summary">
        <p className="text-sm text-slate-800">{generation.summary}</p>
        <p className="mt-2 text-sm text-slate-600">{generation.story_summary}</p>
      </SectionCard>

      <TestCaseFilters value={filters} onChange={setFilters} />

      <SectionCard title={`Test cases (${filtered.length})`}>
        {filtered.length === 0 ? (
          <p className="text-sm text-slate-500">
            No test cases match the current filters.
          </p>
        ) : (
          <ul className="space-y-3">
            {filtered.map((item) => (
              <TestCaseCard key={item.test_case_id} testCase={item} />
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard title="Skipped requirements">
        {generation.skipped_requirements.length === 0 ? (
          <p className="text-sm text-slate-500">No requirements were skipped.</p>
        ) : (
          <ul className="space-y-3">
            {generation.skipped_requirements.map((item) => (
              <li key={item.requirement_id} className="text-sm">
                <p className="font-mono text-xs text-slate-500">{item.requirement_id}</p>
                <p className="mt-1 text-slate-800">{item.description}</p>
                <p className="mt-1 text-slate-500">{item.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  )
}
