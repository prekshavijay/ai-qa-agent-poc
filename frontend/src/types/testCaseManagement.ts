import type {
  AutomationSuitability,
  TestCaseGenerationResponse,
  TestCaseStep,
  TestPriority,
  TestType,
} from './testCases'
import type { RequirementAnalysisResponse } from './requirements'

export type ReviewStatus =
  | 'pending_review'
  | 'approved'
  | 'rejected'
  | 'needs_clarification'

export type ReviewAction =
  | 'approve'
  | 'reject'
  | 'request_clarification'
  | 'edit'
  | 'save'

export type ManagedTestCaseVersion = {
  version_number: number
  title: string
  objective: string
  test_type: TestType
  priority: TestPriority
  preconditions: string[]
  test_data: string[]
  steps: TestCaseStep[]
  expected_result: string
  automation_suitability: AutomationSuitability
  assumptions: string[]
  needs_clarification: boolean
  is_original: boolean
  is_approved_snapshot: boolean
  created_at: string
}

export type ManagedTestCaseReview = {
  review_action: ReviewAction
  version_number: number
  reviewer_id: string | null
  comments: string | null
  created_at: string
}

export type ManagedTestCase = {
  test_case_id: string
  story_id: string
  requirement_id: string
  acceptance_criterion_id: string | null
  current_version: number
  review_status: ReviewStatus
  title: string
  objective: string
  test_type: TestType
  priority: TestPriority
  preconditions: string[]
  test_data: string[]
  steps: TestCaseStep[]
  expected_result: string
  automation_suitability: AutomationSuitability
  assumptions: string[]
  needs_clarification: boolean
  created_at: string
  updated_at: string
  original_version: ManagedTestCaseVersion | null
}

export type StoryTestCaseSummary = {
  story_id: string
  total: number
  pending_review: number
  approved: number
  rejected: number
  needs_clarification: number
  test_cases: ManagedTestCase[]
}

export type SaveGeneratedTestCasesRequest = {
  generation: TestCaseGenerationResponse
  analysis?: RequirementAnalysisResponse
  valid_requirement_ids?: string[]
  valid_acceptance_criterion_ids?: string[]
}

export type SaveGeneratedTestCasesResponse = {
  story_id: string
  saved_count: number
  skipped_duplicates: number
  test_cases: ManagedTestCase[]
}

export type TestCaseEditRequest = {
  title: string
  objective: string
  test_type: TestType
  priority: TestPriority
  preconditions: string[]
  test_data: string[]
  steps: TestCaseStep[]
  expected_result: string
  automation_suitability: AutomationSuitability
  assumptions: string[]
  needs_clarification: boolean
  requirement_id?: string | null
  acceptance_criterion_id?: string | null
  reviewer_id?: string | null
  comments?: string | null
}

export type ReviewerActionRequest = {
  reviewer_id?: string | null
  comments?: string | null
}

export type TestCaseManagementHealth = {
  status: string
  module: string
  note: string
}
