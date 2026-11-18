# Architecture — AI QA Agent POC

## Purpose

This document describes the foundational architecture for the AI QA Agent POC.
The system is intended to assist the full software QA lifecycle:

1. User story creation
2. Test case generation
3. Manual QA support
4. PR validation
5. Automated testing
6. Final QA reporting

Only the foundation (API shell, DB wiring, frontend shell, LLM abstraction) is
implemented in Stage 1. Domain features will be added incrementally.

## High-level layout

```
ai-qa-agent-poc/
├── backend/          # FastAPI application
├── frontend/         # React + Vite SPA
└── docs/             # Architecture and roadmap
```

## Backend layers

| Layer | Path | Responsibility |
|-------|------|----------------|
| API | `app/api/` | HTTP routes only; thin controllers |
| Schemas | `app/schemas/` | Pydantic request/response models |
| Services | `app/services/` | Business / domain logic |
| Agents | `app/agents/` | Agent orchestration (separate from business logic) |
| Integrations | `app/integrations/` | External systems (LLM, Jira, Git, SonarQube, …) |
| Models | `app/models/` | SQLAlchemy ORM entities |
| Database | `app/database/` | Engine, sessions, migrations hook points |
| Core | `app/core/` | Config, logging, exceptions |

### Separation of concerns

- **Routes** stay thin. Requirement analysis and test case generation routes call their agents.
- **Agents** orchestrate validation, services, and integrations.
- **Integrations** wrap third-party APIs behind stable interfaces.
- **Services** own business rules. The requirement analysis service decides what is a requirement and rejects statements that are not in the story. The test case generation service maps only existing requirement IDs into cases and does not invent unsupported behaviour.


## Database strategy

- **POC default:** SQLite via `DATABASE_URL=sqlite:///./qa_agent.db`
- **Future:** set `DATABASE_URL` to a PostgreSQL DSN (e.g. `postgresql+psycopg2://...`)
- SQLAlchemy 2.x is used so the ORM layer stays engine-agnostic.
- SQLite-specific options (`check_same_thread`, foreign key PRAGMA) are applied only when the URL is SQLite.

## LLM integration

`app/integrations/llm/` defines a provider-agnostic contract:

- `LLMClient` — abstract interface (`complete`, `is_available`)
- `get_llm_client()` — factory driven by `LLM_PROVIDER`
- `MockLLMClient` — deterministic provider used when `LLM_PROVIDER` is empty or `mock`. It returns structured JSON and records that no external model was called.
- No API keys are hardcoded; credentials come from environment variables
- A real vendor adapter can replace the mock later by registering it in `get_llm_client()` without changing the requirement analysis service

## Frontend

- React + TypeScript + Vite
- Tailwind CSS for styling
- `src/services/` for API clients
- `src/pages/`, `src/components/`, `src/hooks/`, `src/types/` for UI structure

## Configuration

All runtime settings are loaded from environment variables (see `backend/.env.example`)
via `pydantic-settings`. Copy `.env.example` to `.env` for local development.

## Error handling & logging

- Structured JSON error responses (`code`, `message`, `details`)
- Global handlers for domain, HTTP, validation, and unexpected errors
- Logging configured from `LOG_LEVEL` / `DEBUG`
