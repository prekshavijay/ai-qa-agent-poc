/** Shared frontend TypeScript types. */

export type ApiError = {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}
