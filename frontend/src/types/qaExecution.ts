export type ExecutionRunStatus = 'queued' | 'running' | 'completed' | 'failed'

export type ExecutionResultStatus = 'passed' | 'failed' | 'blocked' | 'not_run'

export type TriggerSource = 'manual'

export type ExecutionResult = {
  id: number
  run_id: string
  test_case_id: string
  title: string
  expected_result: string
  approved_version_id: number
  approved_version_number: number
  status: ExecutionResultStatus
  actual_result: string | null
  error_details: string | null
  evidence: Record<string, unknown>
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  created_at: string
  updated_at: string
}

export type ExecutionRun = {
  run_id: string
  story_id: string
  status: ExecutionRunStatus
  trigger_source: TriggerSource
  started_at: string | null
  completed_at: string | null
  total_test_cases: number
  passed_count: number
  failed_count: number
  blocked_count: number
  not_run_count: number
  created_at: string
  updated_at: string
}

export type ExecutionRunDetail = ExecutionRun & {
  results: ExecutionResult[]
}

export type ExecutionRunList = {
  total: number
  runs: ExecutionRun[]
}

export type CreateExecutionRunRequest = {
  story_id: string
  test_case_ids: string[]
  trigger_source?: TriggerSource
}

export type RecordExecutionResultRequest = {
  test_case_id: string
  status: ExecutionResultStatus
  actual_result?: string | null
  error_details?: string | null
  evidence?: Record<string, unknown> | null
}

export type QaExecutionHealth = {
  status: 'ok'
  module: 'qa_execution'
  note: string
}
