import type { ApiError } from '../types'
import type {
  CreateExecutionRunRequest,
  ExecutionRunDetail,
  ExecutionRunList,
  QaExecutionHealth,
  RecordExecutionResultRequest,
} from '../types/qaExecution'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiRequestError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
  }
}

function messageFromBody(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'error' in body) {
    const error = (body as ApiError).error
    const details = error?.details?.errors
    if (Array.isArray(details) && details.length > 0) {
      const first = details[0] as { msg?: string; loc?: Array<string | number> }
      if (first?.msg) {
        const loc = Array.isArray(first.loc)
          ? first.loc.filter((part) => part !== 'body').join('.')
          : ''
        return loc ? `${loc}: ${first.msg}` : first.msg
      }
    }
    if (error?.message) {
      const testCases = error.details?.test_cases
      const testCaseIds = error.details?.test_case_ids
      if (Array.isArray(testCases) && testCases.length > 0) {
        const summary = testCases
          .map((item) => {
            const row = item as { test_case_id?: string; review_status?: string }
            return row.test_case_id
              ? `${row.test_case_id} (${row.review_status ?? 'unknown'})`
              : ''
          })
          .filter(Boolean)
          .join(', ')
        return summary ? `${error.message}: ${summary}` : error.message
      }
      if (Array.isArray(testCaseIds) && testCaseIds.length > 0) {
        return `${error.message}: ${testCaseIds.join(', ')}`
      }
      return error.message
    }
  }
  return `Request failed (${status})`
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiRequestError('Unable to reach the QA execution service.', 0)
  }

  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      body = null
    }
    throw new ApiRequestError(messageFromBody(body, response.status), response.status)
  }

  return response.json() as Promise<T>
}

export function fetchExecutionHealth(): Promise<QaExecutionHealth> {
  return requestJson<QaExecutionHealth>('/api/qa-execution/health')
}

export function fetchExecutionRuns(storyId?: string): Promise<ExecutionRunList> {
  const params = new URLSearchParams()
  if (storyId?.trim()) {
    params.set('story_id', storyId.trim())
  }
  const query = params.toString()
  return requestJson<ExecutionRunList>(
    query ? `/api/qa-execution/runs?${query}` : '/api/qa-execution/runs',
  )
}

export function fetchExecutionRun(runId: string): Promise<ExecutionRunDetail> {
  return requestJson<ExecutionRunDetail>(
    `/api/qa-execution/runs/${encodeURIComponent(runId)}`,
  )
}

export function createExecutionRun(
  payload: CreateExecutionRunRequest,
): Promise<ExecutionRunDetail> {
  return requestJson<ExecutionRunDetail>('/api/qa-execution/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function recordExecutionResult(
  runId: string,
  payload: RecordExecutionResultRequest,
): Promise<ExecutionRunDetail> {
  return requestJson<ExecutionRunDetail>(
    `/api/qa-execution/runs/${encodeURIComponent(runId)}/results`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}
