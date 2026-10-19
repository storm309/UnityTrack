# UnityTrack

> **AI-Powered Decision-Support Platform for Indian Railways Maintenance Planning**

UnityTrack unifies maintenance planning across three key Indian Railways departments:
1. **Engineering (ENG)**: Civil track renewals, deep screening, tamping, weld repairs.
2. **Traction Distribution (TRD)**: Overhead Equipment (OHE) maintenance, contact wire replacement, power blocks.
3. **Signal & Telecom (SNT)**: Interlocking, point machines, track circuits, axle counters, signals.

UnityTrack scores task priority with an explainable model, bundles compatible multi-department maintenance windows, and computes conflict-free schedules using Google OR-Tools CP-SAT constraint programming.

---

## Architecture Overview

```
UnityTrack_Project/
├── backend/
│   ├── alembic/              # Database migration definitions & env
│   ├── app/
│   │   ├── api/              # FastAPI routers (health, priority, bundles, plans)
│   │   ├── optimizer/        # PURE PYTHON constraint optimizer (NO FastAPI/DB deps)
│   │   ├── schemas/          # Pydantic v2 data models
│   │   ├── config.py         # Settings & environment configuration
│   │   ├── database.py       # SQLAlchemy 2.0 engine & session lifecycle
│   │   ├── export_openapi.py # Schema exporter for TypeScript type generation
│   │   └── main.py           # FastAPI application factory
│   ├── tests/                # Pytest test suite with in-memory SQLite fixtures
│   ├── Dockerfile            # Container definition for backend
│   ├── pyproject.toml        # Ruff, MyPy, and Pytest configuration
│   └── requirements.txt      # Fully pinned Python dependencies
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router (Layout, Page, Providers)
│   │   └── lib/              # Generated TypeScript API types & typed client
│   ├── Dockerfile            # Container definition for frontend
│   ├── package.json          # Dependencies, scripts (gen:api, test, lint)
│   └── vitest.config.ts      # Vitest component testing configuration
├── docs/                     # Architecture & specifications
├── .github/workflows/ci.yml  # GitHub Actions CI matrix
├── docker-compose.yml        # PostgreSQL + FastAPI + Next.js orchestration
├── Makefile                  # Standardized development workflows
└── .env.example              # Canonical environment variable template
```

---

## Quickstart

### Option 1: Docker Compose (All Services)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start PostgreSQL, Backend, and Frontend
docker compose up --build
```
- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API & OpenAPI Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

### Option 2: Local Development (Without Docker)

#### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Type Contract Generation

UnityTrack strictly enforces end-to-end type safety between FastAPI and Next.js. API types are generated from OpenAPI schemas to avoid drift:

```bash
# Export schema from backend
cd backend && python -m app.export_openapi

# Generate TypeScript client types in frontend
cd frontend && npm run gen:api
```

---

## Verification & Testing

### Backend
```bash
cd backend
python -m pytest -v          # Run unit & integration tests
ruff check .                 # Run linter
mypy app tests               # Run static type checker
```

### Frontend
```bash
cd frontend
npm test                     # Run Vitest component tests
npm run lint                 # Run ESLint
npm run typecheck            # Run tsc --noEmit
```

### Monorepo Makefile Commands
```bash
make test                    # Run all tests (backend + frontend)
make lint                    # Run all linters and typecheckers
```
