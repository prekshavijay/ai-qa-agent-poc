import type {
  ExecutionResultStatus,
  ExecutionRunStatus,
} from '../../types/qaExecution'

const RUN_LABEL: Record<ExecutionRunStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
}

const RUN_CLASS: Record<ExecutionRunStatus, string> = {
  queued: 'bg-slate-50 text-slate-700 ring-slate-200',
  running: 'bg-sky-50 text-sky-800 ring-sky-200',
  completed: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  failed: 'bg-rose-50 text-rose-800 ring-rose-200',
}

const RESULT_LABEL: Record<ExecutionResultStatus, string> = {
  passed: 'Passed',
  failed: 'Failed',
  blocked: 'Blocked',
  not_run: 'Not run',
}

const RESULT_CLASS: Record<ExecutionResultStatus, string> = {
  passed: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  failed: 'bg-rose-50 text-rose-800 ring-rose-200',
  blocked: 'bg-amber-50 text-amber-800 ring-amber-200',
  not_run: 'bg-slate-50 text-slate-700 ring-slate-200',
}

export function RunStatusBadge({ status }: { status: ExecutionRunStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${RUN_CLASS[status]}`}
    >
      {RUN_LABEL[status]}
    </span>
  )
}

export function ResultStatusBadge({ status }: { status: ExecutionResultStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${RESULT_CLASS[status]}`}
    >
      {RESULT_LABEL[status]}
    </span>
  )
}
