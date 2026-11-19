import type { ApiError } from '../types'
import type {
  ManagedTestCase,
  ManagedTestCaseReview,
  ManagedTestCaseVersion,
  ReviewerActionRequest,
  SaveGeneratedTestCasesRequest,
  SaveGeneratedTestCasesResponse,
  StoryTestCaseSummary,
  TestCaseEditRequest,
  TestCaseManagementHealth,
} from '../types/testCaseManagement'

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
    throw new ApiRequestError('Unable to reach the test case management service.', 0)
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

function withStoryQuery(path: string, storyId?: string): string {
  if (!storyId) {
    return path
  }
  const params = new URLSearchParams({ story_id: storyId })
  return `${path}?${params.toString()}`
}

export function fetchManagementHealth(): Promise<TestCaseManagementHealth> {
  return requestJson<TestCaseManagementHealth>('/api/test-case-management/health')
}

export function saveGeneratedTestCases(
  payload: SaveGeneratedTestCasesRequest,
): Promise<SaveGeneratedTestCasesResponse> {
  return requestJson<SaveGeneratedTestCasesResponse>('/api/test-case-management/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function fetchStoryTestCases(storyId: string): Promise<StoryTestCaseSummary> {
  return requestJson<StoryTestCaseSummary>(
    `/api/test-case-management/stories/${encodeURIComponent(storyId)}`,
  )
}

export function fetchApprovedTestCases(storyId: string): Promise<ManagedTestCase[]> {
  return requestJson<ManagedTestCase[]>(
    `/api/test-case-management/stories/${encodeURIComponent(storyId)}/approved`,
  )
}

export function fetchManagedTestCase(
  testCaseId: string,
  storyId?: string,
): Promise<ManagedTestCase> {
  return requestJson<ManagedTestCase>(
    withStoryQuery(
      `/api/test-case-management/${encodeURIComponent(testCaseId)}`,
      storyId,
    ),
  )
}

export function updateManagedTestCase(
  testCaseId: string,
  payload: TestCaseEditRequest,
  storyId?: string,
): Promise<ManagedTestCase> {
  return requestJson<ManagedTestCase>(
    withStoryQuery(
      `/api/test-case-management/${encodeURIComponent(testCaseId)}`,
      storyId,
    ),
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function approveTestCase(
  testCaseId: string,
  payload: ReviewerActionRequest,
  storyId?: string,
): Promise<ManagedTestCase> {
  return requestJson<ManagedTestCase>(
    withStoryQuery(
      `/api/test-case-management/${encodeURIComponent(testCaseId)}/approve`,
      storyId,
    ),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function rejectTestCase(
  testCaseId: string,
  payload: ReviewerActionRequest & { comments: string },
  storyId?: string,
): Promise<ManagedTestCase> {
  return requestJson<ManagedTestCase>(
    withStoryQuery(
      `/api/test-case-management/${encodeURIComponent(testCaseId)}/reject`,
      storyId,
    ),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function clarifyTestCase(
  testCaseId: string,
  payload: ReviewerActionRequest & { comments: string },
  storyId?: string,
): Promise<ManagedTestCase> {
  return requestJson<ManagedTestCase>(
    withStoryQuery(
      `/api/test-case-management/${encodeURIComponent(testCaseId)}/clarify`,
      storyId,
    ),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function fetchVersionHistory(
  testCaseId: string,
  storyId?: string,
): Promise<ManagedTestCaseVersion[]> {
  return requestJson<ManagedTestCaseVersion[]>(
    withStoryQuery(
      `/api/test-case-management/${encodeURIComponent(testCaseId)}/versions`,
      storyId,
    ),
  )
}

export function fetchReviewHistory(
  testCaseId: string,
  storyId?: string,
): Promise<ManagedTestCaseReview[]> {
  return requestJson<ManagedTestCaseReview[]>(
    withStoryQuery(
      `/api/test-case-management/${encodeURIComponent(testCaseId)}/reviews`,
      storyId,
    ),
  )
}
