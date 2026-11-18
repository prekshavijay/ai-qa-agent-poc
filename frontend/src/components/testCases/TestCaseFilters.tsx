import type { TestPriority, TestType } from '../../types/testCases'

export type TestCaseFilterState = {
  testType: TestType | 'all'
  priority: TestPriority | 'all'
  clarificationOnly: boolean
}

type TestCaseFiltersProps = {
  value: TestCaseFilterState
  onChange: (next: TestCaseFilterState) => void
}

const TEST_TYPES: Array<TestType | 'all'> = [
  'all',
  'positive',
  'negative',
  'boundary',
  'edge',
  'integration',
]

const PRIORITIES: Array<TestPriority | 'all'> = [
  'all',
  'critical',
  'high',
  'medium',
  'low',
]

function label(value: string): string {
  return value.replaceAll('_', ' ')
}

export function TestCaseFilters({ value, onChange }: TestCaseFiltersProps) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <label className="text-sm">
        <span className="font-medium text-slate-700">Test type</span>
        <select
          value={value.testType}
          onChange={(event) =>
            onChange({
              ...value,
              testType: event.target.value as TestType | 'all',
            })
          }
          className="mt-1 block w-40 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
        >
          {TEST_TYPES.map((item) => (
            <option key={item} value={item}>
              {label(item)}
            </option>
          ))}
        </select>
      </label>

      <label className="text-sm">
        <span className="font-medium text-slate-700">Priority</span>
        <select
          value={value.priority}
          onChange={(event) =>
            onChange({
              ...value,
              priority: event.target.value as TestPriority | 'all',
            })
          }
          className="mt-1 block w-40 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
        >
          {PRIORITIES.map((item) => (
            <option key={item} value={item}>
              {label(item)}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={value.clarificationOnly}
          onChange={(event) =>
            onChange({
              ...value,
              clarificationOnly: event.target.checked,
            })
          }
          className="rounded border-slate-300"
        />
        Needs clarification only
      </label>
    </div>
  )
}
