import { useState } from 'react'
import type { FormEvent } from 'react'
import type { StoryInput } from '../../types/requirements'

type StoryFormProps = {
  loading: boolean
  onSubmit: (story: StoryInput) => void
}

export function StoryForm({ loading, onSubmit }: StoryFormProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [storyId, setStoryId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [criteria, setCriteria] = useState<string[]>([''])
  const [titleError, setTitleError] = useState<string | null>(null)

  function updateCriterion(index: number, value: string) {
    setCriteria((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)))
  }

  function addCriterion() {
    setCriteria((current) => [...current, ''])
  }

  function removeCriterion(index: number) {
    setCriteria((current) => {
      if (current.length === 1) {
        return ['']
      }
      return current.filter((_, itemIndex) => itemIndex !== index)
    })
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const cleanedTitle = title.trim()
    if (!cleanedTitle) {
      setTitleError('Title is required.')
      return
    }
    setTitleError(null)

    const story: StoryInput = {
      title: cleanedTitle,
      description: description.trim(),
      acceptance_criteria: criteria.map((item) => item.trim()).filter(Boolean),
    }
    const cleanedStoryId = storyId.trim()
    const cleanedProjectId = projectId.trim()
    if (cleanedStoryId) {
      story.story_id = cleanedStoryId
    }
    if (cleanedProjectId) {
      story.project_id = cleanedProjectId
    }
    onSubmit(story)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="font-medium text-slate-700">Story ID (optional)</span>
          <input
            value={storyId}
            onChange={(event) => setStoryId(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
            autoComplete="off"
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-700">Project ID (optional)</span>
          <input
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
            autoComplete="off"
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="font-medium text-slate-700">Story title</span>
        <input
          value={title}
          onChange={(event) => {
            setTitle(event.target.value)
            if (titleError) {
              setTitleError(null)
            }
          }}
          aria-invalid={titleError ? true : undefined}
          aria-describedby={titleError ? 'title-error' : undefined}
          className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
          autoComplete="off"
        />
        {titleError ? (
          <p id="title-error" className="mt-1 text-sm text-rose-700">
            {titleError}
          </p>
        ) : null}
      </label>

      <label className="block text-sm">
        <span className="font-medium text-slate-700">Story description</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={5}
          className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
        />
      </label>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-slate-700">Acceptance criteria</legend>
        {criteria.map((criterion, index) => (
          <div key={index} className="flex items-start gap-2">
            <label className="block flex-1 text-sm">
              <span className="sr-only">Acceptance criterion {index + 1}</span>
              <input
                value={criterion}
                onChange={(event) => updateCriterion(index, event.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
              />
            </label>
            <button
              type="button"
              onClick={() => removeCriterion(index)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              aria-label={`Remove acceptance criterion ${index + 1}`}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={addCriterion}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          Add acceptance criterion
        </button>
      </fieldset>

      <button
        type="submit"
        disabled={loading}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {loading ? 'Analyzing requirements…' : 'Analyze Requirements'}
      </button>
    </form>
  )
}
