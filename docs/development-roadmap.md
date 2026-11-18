# Development Roadmap — AI QA Agent POC

Incremental delivery plan. **Do not implement future stages until the current stage is approved.**

## Stage 1 — Project foundation (current)

- [x] Backend scaffolding (FastAPI, Pydantic, SQLAlchemy)
- [x] Frontend scaffolding (React, TypeScript, Vite, Tailwind)
- [x] SQLite + SQLAlchemy with PostgreSQL-ready `DATABASE_URL`
- [x] Environment-based configuration
- [x] Logging and error handling
- [x] Health-check endpoint (`/health`)
- [x] Provider-agnostic LLM integration stub
- [x] README, `.gitignore`, architecture docs

## Stage 2 — Core domain & persistence

- User story / requirement models and CRUD APIs
- Test case models and basic CRUD
- Frontend pages for creating and listing stories / cases
- Database migrations (Alembic)

## Stage 3 — LLM wiring

- Register a concrete LLM adapter behind `LLMClient`
- Prompt templates for story refinement and test case generation
- Streaming / non-streaming completion support as needed
- Cost / token logging (optional for POC)

## Stage 4 — Manual QA assistance

- Manual test execution checklist UI
- Evidence / notes capture
- Defect draft generation from failed steps

## Stage 5 — PR validation

- Git provider integration (GitHub/GitLab abstraction)
- PR diff ingestion and risk summary
- Suggested regression test selection

## Stage 6 — Automated testing & quality gates

- Test runner integration (e.g. pytest / Playwright hooks)
- Optional SonarQube / static analysis adapter
- Gate status aggregation

## Stage 7 — QA reporting

- Run / release report generation
- Export (Markdown / PDF) and dashboard summary
- Traceability: story → cases → results → PR

## Out of scope for early stages

- Production multi-tenant auth
- Hardcoded AI vendor lock-in
- Full CI/CD productization
