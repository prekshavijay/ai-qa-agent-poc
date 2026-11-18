import type { RequirementAnalysisResponse } from '../types/requirements'

const ANALYSIS_STORAGE_KEY = 'qa_agent_requirement_analysis'

export function readStoredAnalysis(): RequirementAnalysisResponse | null {
  try {
    const raw = sessionStorage.getItem(ANALYSIS_STORAGE_KEY)
    if (!raw) {
      return null
    }
    return JSON.parse(raw) as RequirementAnalysisResponse
  } catch {
    return null
  }
}

export function storeAnalysis(analysis: RequirementAnalysisResponse) {
  sessionStorage.setItem(ANALYSIS_STORAGE_KEY, JSON.stringify(analysis))
}

export function clearStoredAnalysis() {
  sessionStorage.removeItem(ANALYSIS_STORAGE_KEY)
}
