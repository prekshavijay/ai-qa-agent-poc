import type { AnalysisStatus, TestabilityStatus } from '../../types/requirements'

const STATUS_LABEL: Record<AnalysisStatus, string> = {
  complete: 'Complete',
  needs_clarification: 'Needs clarification',
  insufficient_input: 'Insufficient input',
}

const STATUS_CLASS: Record<AnalysisStatus, string> = {
  complete: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  needs_clarification: 'bg-amber-50 text-amber-800 ring-amber-200',
  insufficient_input: 'bg-rose-50 text-rose-800 ring-rose-200',
}

export function StatusBadge({ status }: { status: AnalysisStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${STATUS_CLASS[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}

export function formatToken(value: TestabilityStatus | string): string {
  return value.replaceAll('_', ' ')
}
