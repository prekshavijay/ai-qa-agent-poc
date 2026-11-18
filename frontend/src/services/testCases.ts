import type { ApiError } from '../types'
import type { RequirementAnalysisResponse } from '../types/requirements'
import type {
  TestCaseGenerationHealth,
  TestCaseGenerationResponse,
} from '../types/testCases'

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
    throw new ApiRequestError('Unable to reach the test case generation service.', 0)
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

export function generateTestCases(
  analysis: RequirementAnalysisResponse,
): Promise<TestCaseGenerationResponse> {
  return requestJson<TestCaseGenerationResponse>('/api/test-cases/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(analysis),
  })
}

export function fetchTestCaseHealth(): Promise<TestCaseGenerationHealth> {
  return requestJson<TestCaseGenerationHealth>('/api/test-cases/health')
}
