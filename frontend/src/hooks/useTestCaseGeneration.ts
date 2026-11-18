import { useState } from 'react'
import { analyzeRequirements } from '../services/requirements'
import { generateTestCases } from '../services/testCases'
import type { RequirementAnalysisResponse, StoryInput } from '../types/requirements'
import type { TestCaseGenerationResponse } from '../types/testCases'

export function useTestCaseGeneration() {
  const [analysis, setAnalysis] = useState<RequirementAnalysisResponse | null>(null)
  const [result, setResult] = useState<TestCaseGenerationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [generating, setGenerating] = useState(false)

  async function analyze(story: StoryInput) {
    setAnalyzing(true)
    setError(null)
    setResult(null)
    try {
      const next = await analyzeRequirements(story)
      setAnalysis(next)
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : 'Requirement analysis failed.'
      setError(message)
      setAnalysis(null)
    } finally {
      setAnalyzing(false)
    }
  }

  function loadAnalysis(next: RequirementAnalysisResponse) {
    setAnalysis(next)
    setResult(null)
    setError(null)
  }

  async function generate(fromAnalysis?: RequirementAnalysisResponse) {
    const payload = fromAnalysis ?? analysis
    if (!payload) {
      setError('Analyze a user story first, then generate test cases.')
      return
    }
    setGenerating(true)
    setError(null)
    setResult(null)
    try {
      const generation = await generateTestCases(payload)
      setAnalysis(payload)
      setResult(generation)
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : 'Test case generation failed.'
      setError(message)
    } finally {
      setGenerating(false)
    }
  }

  return {
    analysis,
    result,
    error,
    analyzing,
    generating,
    analyze,
    generate,
    loadAnalysis,
  }
}
