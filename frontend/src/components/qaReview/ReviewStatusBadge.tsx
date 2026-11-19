import type { ReviewStatus } from '../../types/testCaseManagement'

const STATUS_LABEL: Record<ReviewStatus, string> = {
  pending_review: 'Pending review',
  approved: 'Approved',
  rejected: 'Rejected',
  needs_clarification: 'Needs clarification',
}

const STATUS_CLASS: Record<ReviewStatus, string> = {
  pending_review: 'bg-sky-50 text-sky-800 ring-sky-200',
  approved: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  rejected: 'bg-rose-50 text-rose-800 ring-rose-200',
  needs_clarification: 'bg-amber-50 text-amber-800 ring-amber-200',
}

export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${STATUS_CLASS[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}
