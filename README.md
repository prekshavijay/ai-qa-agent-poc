# AI QA Agent POC

Proof-of-concept foundation for an AI system that assists the software QA lifecycle — from user stories through test generation, manual QA, PR validation, automation, and reporting.

**Stage 1 (this commit scope):** project scaffolding only. No agents, Jira, PR, test runners, or SonarQube integrations yet.

## Folder structure

```
ai-qa-agent-poc/
├── backend/
│   ├── app/
│   │   ├── api/            # HTTP routes (health, future domain APIs)
│   │   ├── agents/         # Agent orchestration (empty placeholder)
│   │   ├── services/       # Business logic (empty placeholder)
│   │   ├── integrations/   # External adapters (LLM stub)
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── core/           # Config, logging, exceptions
│   │   ├── database/       # Engine & sessions (SQLite → PostgreSQL ready)
│   │   └── main.py         # FastAPI entrypoint
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/
│       ├── types/
│       └── hooks/
├── docs/
│   ├── architecture.md
│   └── development-roadmap.md
└── README.md
```

## Prerequisites

- Python 3.9+ (3.11+ recommended)
- Node.js 20+ and npm
- (Optional) PostgreSQL later — not required for the SQLite POC

## Install dependencies

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### Frontend

```bash
cd frontend
npm install
```

## Configuration

Copy `backend/.env.example` to `backend/.env` and adjust as needed.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Default `sqlite:///./qa_agent.db`; later use a PostgreSQL DSN |
| `CORS_ORIGINS` | Allowed frontend origins |
| `LLM_PROVIDER` / `LLM_API_KEY` / … | Left empty until an LLM adapter is wired |
| `VITE_API_BASE_URL` | Optional frontend override; leave unset to use Vite proxy |

**Do not commit `.env` or API keys.**

## Run locally

Open two terminals.

### Backend (http://127.0.0.1:8000)

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Frontend (http://127.0.0.1:5173)

```bash
cd frontend
npm run dev
```

The Vite dev server proxies `/health` and `/api` to the backend.

## Requirement analysis

`POST /api/requirements/analyze` accepts a user story and returns structured requirements, ambiguities, and clarification questions.

`GET /api/requirements/health` reports whether the deterministic mock provider is active.

When `LLM_PROVIDER` is empty or `mock`, the requirement analysis agent uses that mock. The mock does not call an external model. Extraction rules live in the requirement analysis service and keep a statement only when it is written in the story. The frontend **Requirement Analysis** page submits stories to this endpoint.

## Test case generation

`POST /api/test-cases/generate` accepts a `RequirementAnalysisResponse` and returns structured, traceable test cases (positive, negative, boundary, edge, and integration where supported).

`GET /api/test-cases/health` reports whether the deterministic mock provider is active for generation.

Generation consumes the requirement analysis output only — it does not re-analyse or invent requirements. The frontend **Test Case Generation** page can analyze a story first, or continue from a completed Requirement Analysis result.

## QA execution

`POST /api/qa-execution/runs` creates a manual execution run for selected test cases that are currently approved. Each case is stored as `not_run` and linked to that approved version. Later edits do not change the link.

`POST /api/qa-execution/runs/{run_id}/results` records a manual result and recalculates passed, failed, blocked, and not-run counts. The run stays incomplete while any case is `not_run`, and becomes `completed` only when every case is `passed`, `failed`, or `blocked`.

`GET /api/qa-execution/health` reports that automated browser and API execution is not implemented yet. The frontend **QA Execution** page lists runs and records results by hand.

## Verify health

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{
  "status": "ok",
  "service": "AI QA Agent POC",
  "environment": "development",
  "version": "0.1.0"
}
```

Backend unit smoke test:

```bash
cd backend
source .venv/bin/activate
pytest
```

## Database notes

- Local POC uses **SQLite** (file created on first startup).
- To migrate later, set `DATABASE_URL` to PostgreSQL and install a driver such as `psycopg2-binary` or `psycopg`. Application code is written against SQLAlchemy and does not hardcode SQLite beyond connection helpers.

## What is intentionally not included yet

- AI agents and prompts
- Jira / Git / SonarQube integrations
- Automated Playwright execution and AI-generated test scripts
- Alembic migrations (planned for Stage 2)
- Authentication

See [docs/development-roadmap.md](docs/development-roadmap.md) for the staged plan.
