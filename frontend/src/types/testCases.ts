import type { RequirementAnalysisResponse } from './requirements'

export type TestType = 'positive' | 'negative' | 'boundary' | 'edge' | 'integration'

export type TestPriority = 'critical' | 'high' | 'medium' | 'low'

export type AutomationSuitability = 'suitable' | 'partially_suitable' | 'manual_only'

export type GenerationStatus =
  | 'complete'
  | 'partial'
  | 'needs_clarification'
  | 'no_test_cases'

export type TestCaseStep = {
  step_number: number
  action: string
  expected_result: string
}

export type TestCase = {
  test_case_id: string
  title: string
  objective: string
  requirement_id: string
  acceptance_criterion_id: string | null
  test_type: TestType
  priority: TestPriority
  preconditions: string[]
  test_data: string[]
  steps: TestCaseStep[]
  expected_result: string
  automation_suitability: AutomationSuitability
  assumptions: string[]
  needs_clarification: boolean
}

export type SkippedRequirement = {
  requirement_id: string
  description: string
  reason: string
}

export type TestCaseGenerationRequest = RequirementAnalysisResponse

export type PersistenceStatus = 'saved' | 'not_required' | 'failed'

export type PersistenceError = {
  code: string
  message: string
}

export type PersistenceResult = {
  status: PersistenceStatus
  saved_count: number
  skipped_duplicates: number
  warning: string | null
  error: PersistenceError | null
}

export type TestCaseGenerationResponse = {
  story_id: string
  story_summary: string
  test_cases: TestCase[]
  skipped_requirements: SkippedRequirement[]
  generation_status: GenerationStatus
  provider: string
  provider_note: string
  summary: string
  persistence?: PersistenceResult
}

export type TestCaseGenerationHealth = {
  status: string
  module: string
  llm_provider: string
  llm_available: boolean
  mock_implementation: boolean
  note: string
}
