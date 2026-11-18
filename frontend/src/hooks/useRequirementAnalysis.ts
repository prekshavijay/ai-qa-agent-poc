import { useState } from 'react'
import { analyzeRequirements } from '../services/requirements'
import type { RequirementAnalysisResponse, StoryInput } from '../types/requirements'

export function useRequirementAnalysis() {
  const [result, setResult] = useState<RequirementAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function analyze(story: StoryInput) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const analysis = await analyzeRequirements(story)
      setResult(analysis)
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : 'Requirement analysis failed.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return { result, error, loading, analyze }
}
