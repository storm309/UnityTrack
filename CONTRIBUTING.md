# Contributing to UnityTrack

Thank you for contributing to UnityTrack! This project is a multi-departmental railway maintenance intelligence platform built with:
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, Google OR-Tools CP-SAT
- **Frontend:** Next.js 16 (App Router), React 19, TanStack Query, Tailwind CSS, Lucide Icons
- **Verification:** Pytest, Ruff, MyPy, Vitest, TypeScript, ESLint

---

## 🚀 Setting Up Your Local Environment

### 1. Backend Setup
```bash
cd backend
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python -m app.seed --seed 42 --reset
python -m uvicorn app.main:app --app-dir . --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to view the web dashboard.

---

## 📋 Project Roadmap & Task Assignments

Please see **[PROJECT_PLAN.md](./PROJECT_PLAN.md)** for:
- Detailed status of all project sections (Sections 0 to 10).
- Specific remaining tasks (Tasks 1 through 5) assigned for group project members.
- Acceptance criteria and step-by-step instructions.

---

## 🧪 Testing & Quality Gates

Always verify all tests and linters pass before opening a pull request or pushing:

```bash
# Backend Quality Checks:
pytest backend/tests -v
ruff check backend
mypy backend/app

# Frontend Quality Checks:
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run lint
```

---

## 📜 Contract Synchronization Rule

If you add or update any FastAPI routes or Pydantic schemas in the backend:
1. Export the OpenAPI specification:
   ```bash
   python backend/export_openapi.py
   ```
2. Re-generate TypeScript API client types:
   ```bash
   npm --prefix frontend run gen:api
   ```
3. Never manually write types in `frontend/src/lib/api-types.ts`.
