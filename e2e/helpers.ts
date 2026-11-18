import type { Page, APIRequestContext } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

export const ARTIFACTS_DIR = path.join(__dirname, '..', 'artifacts', 'test-execution')
export const VIDEO_WEBM = path.join(ARTIFACTS_DIR, 'ai-qa-agent-test-run.webm')
export const VIDEO_MP4 = path.join(ARTIFACTS_DIR, 'ai-qa-agent-test-run.mp4')
export const CONSOLE_LOG = path.join(ARTIFACTS_DIR, 'browser-console.log')
export const RESULTS_JSON = path.join(ARTIFACTS_DIR, 'e2e-observations.json')

export type Observation = {
  scenario: string
  expected: string
  actual: string
  status: 'PASS' | 'FAIL' | 'BLOCKED'
  notes?: string
}

export const AUTH_STORY = {
  storyId: 'AUTH-101',
  projectId: 'AUTH-MODULE',
  title: 'Implement user login functionality',
  description:
    'As a registered user, I want to log in using my email address and password so that I can access my dashboard.',
  acceptanceCriteria: [
    'Users should be able to log in with valid credentials.',
    'Invalid credentials should display an error message.',
    'Email and password fields are mandatory.',
    'Successful login should redirect the user to the dashboard.',
    'Locked accounts should not be allowed to log in.',
  ],
}

export function ensureArtifactsDir(): void {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true })
}

export function attachConsoleCapture(page: Page, lines: string[]): void {
  page.on('console', (msg) => {
    lines.push(`[${msg.type()}] ${msg.text()}`)
  })
  page.on('pageerror', (err) => {
    lines.push(`[pageerror] ${err.message}`)
  })
}

export async function fillStoryForm(
  page: Page,
  story: {
    storyId?: string
    projectId?: string
    title?: string
    description?: string
    acceptanceCriteria?: string[]
  },
): Promise<void> {
  const storyId = page.getByLabel('Story ID (optional)')
  const projectId = page.getByLabel('Project ID (optional)')
  const title = page.getByLabel('Story title')
  const description = page.getByLabel('Story description')

  await storyId.fill(story.storyId ?? '')
  await projectId.fill(story.projectId ?? '')
  await title.fill(story.title ?? '')
  await description.fill(story.description ?? '')

  const criteria = story.acceptanceCriteria ?? []
  const addButton = page.getByRole('button', { name: 'Add acceptance criterion' })
  const fieldset = page.locator('fieldset')

  // Normalize to exactly one empty row, then grow to the desired count.
  let inputs = fieldset.getByRole('textbox')
  while ((await inputs.count()) > 1) {
    const lastIndex = (await inputs.count()) - 1
    await page
      .getByRole('button', { name: `Remove acceptance criterion ${lastIndex + 1}` })
      .click()
    inputs = fieldset.getByRole('textbox')
  }
  await inputs.first().fill('')

  const targetCount = Math.max(criteria.length, 1)
  for (let i = 1; i < targetCount; i += 1) {
    await addButton.click()
  }

  inputs = fieldset.getByRole('textbox')
  const count = await inputs.count()
  for (let i = 0; i < count; i += 1) {
    await inputs.nth(i).fill(criteria[i] ?? '')
  }
}

export async function clearAcceptanceCriteria(page: Page): Promise<void> {
  await fillStoryForm(page, {
    storyId: '',
    projectId: '',
    title: 'placeholder',
    description: '',
    acceptanceCriteria: [],
  })
}

export function writeJson(filePath: string, data: unknown): void {
  ensureArtifactsDir()
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8')
}

export function writeText(filePath: string, content: string): void {
  ensureArtifactsDir()
  fs.writeFileSync(filePath, content, 'utf8')
}

export async function apiGet(request: APIRequestContext, url: string) {
  const response = await request.get(url)
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = await response.text()
  }
  return { status: response.status(), body }
}

export async function apiPost(request: APIRequestContext, url: string, data: unknown) {
  const response = await request.post(url, { data })
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = await response.text()
  }
  return { status: response.status(), body }
}
