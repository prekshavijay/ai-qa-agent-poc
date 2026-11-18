import { SectionCard } from '../ui/SectionCard'
import { formatToken, StatusBadge } from './StatusBadge'
import type {
  FunctionalRequirement,
  NonFunctionalRequirement,
  RequirementAnalysisResponse,
} from '../../types/requirements'

type AnalysisResultsProps = {
  analysis: RequirementAnalysisResponse
  onGenerateTestCases?: () => void
}


function RequirementItems({
  items,
}: {
  items: Array<FunctionalRequirement | NonFunctionalRequirement>
}) {
  if (items.length === 0) {
    return null
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const category = 'category' in item ? item.category : null
        return (
          <li key={item.requirement_id} className="rounded-md border border-slate-200 p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-mono text-slate-700">{item.requirement_id}</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5">{item.priority}</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5">
                {formatToken(item.testability_status)}
              </span>
              {category ? (
                <span className="rounded bg-slate-100 px-1.5 py-0.5">{category}</span>
              ) : null}
            </div>
            <p className="mt-2 text-sm text-slate-800">{item.description}</p>
            {item.source_acceptance_criterion ? (
              <p className="mt-2 text-xs text-slate-500">
                Source acceptance criterion: {item.source_acceptance_criterion}
              </p>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

export function AnalysisResults({
  analysis,
  onGenerateTestCases,
}: AnalysisResultsProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Story</p>
          <p className="font-mono text-sm text-slate-800">{analysis.story_id}</p>
        </div>
        <StatusBadge status={analysis.analysis_status} />
      </div>

      <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
        {analysis.provider_note}
      </p>

      {onGenerateTestCases ? (
        <button
          type="button"
          onClick={onGenerateTestCases}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Generate Test Cases
        </button>
      ) : null}


      <SectionCard title="Story summary">
        <p className="text-sm text-slate-800">{analysis.story_summary}</p>
      </SectionCard>

      <SectionCard title="Functional requirements">
        {analysis.functional_requirements.length === 0 ? (
          <p className="text-sm text-slate-500">
            No functional requirements could be extracted from the story text.
          </p>
        ) : (
          <RequirementItems items={analysis.functional_requirements} />
        )}
      </SectionCard>

      <SectionCard title="Non-functional requirements">
        {analysis.non_functional_requirements.length === 0 ? (
          <p className="text-sm text-slate-500">
            No non-functional requirements were stated in the story.
          </p>
        ) : (
          <RequirementItems items={analysis.non_functional_requirements} />
        )}
      </SectionCard>

      <SectionCard title="Acceptance criteria">
        {analysis.acceptance_criteria.length === 0 ? (
          <p className="text-sm text-slate-500">No acceptance criteria were provided.</p>
        ) : (
          <ul className="space-y-2">
            {analysis.acceptance_criteria.map((criterion) => (
              <li key={criterion.criterion_id} className="text-sm text-slate-800">
                <span className="mr-2 font-mono text-xs text-slate-500">
                  {criterion.criterion_id}
                </span>
                {criterion.description}
                <span className="ml-2 text-xs text-slate-500">
                  {formatToken(criterion.testability_status)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard title="Ambiguities">
        {analysis.ambiguities.length === 0 ? (
          <p className="text-sm text-slate-500">No ambiguous statements were found in the story.</p>
        ) : (
          <ul className="space-y-3">
            {analysis.ambiguities.map((item) => (
              <li key={item.ambiguity_id} className="text-sm">
                <p className="font-mono text-xs text-slate-500">
                  {item.ambiguity_id} · {item.source.replaceAll('_', ' ')}
                </p>
                <p className="mt-1 text-slate-800">{item.statement}</p>
                <p className="mt-1 text-slate-500">{item.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard title="Clarification questions">
        {analysis.clarification_questions.length === 0 ? (
          <p className="text-sm text-slate-500">No clarification questions.</p>
        ) : (
          <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-800">
            {analysis.clarification_questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ol>
        )}
      </SectionCard>
    </div>
  )
}
