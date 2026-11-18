export type Priority = 'high' | 'medium' | 'low'

export type TestabilityStatus = 'testable' | 'partially_testable' | 'not_testable'

export type AnalysisStatus = 'complete' | 'needs_clarification' | 'insufficient_input'

export type StoryInput = {
  title: string
  description: string
  acceptance_criteria: string[]
  story_id?: string
  project_id?: string
}

export type FunctionalRequirement = {
  requirement_id: string
  description: string
  priority: Priority
  source_acceptance_criterion: string | null
  testability_status: TestabilityStatus
}

export type NonFunctionalRequirement = FunctionalRequirement & {
  category: string
}

export type AcceptanceCriterion = {
  criterion_id: string
  description: string
  testability_status: TestabilityStatus
}

export type Ambiguity = {
  ambiguity_id: string
  statement: string
  reason: string
  source: 'title' | 'description' | 'acceptance_criteria'
}

export type RequirementAnalysisResponse = {
  story_id: string
  story_summary: string
  functional_requirements: FunctionalRequirement[]
  non_functional_requirements: NonFunctionalRequirement[]
  acceptance_criteria: AcceptanceCriterion[]
  ambiguities: Ambiguity[]
  clarification_questions: string[]
  analysis_status: AnalysisStatus
  provider: string
  provider_note: string
}

export type RequirementAnalysisHealth = {
  status: string
  module: string
  llm_provider: string
  llm_available: boolean
  mock_implementation: boolean
  note: string
}
