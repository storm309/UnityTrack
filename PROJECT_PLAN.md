# UnityTrack — Group Project Master Plan & Contributor Guide

> **Indian Railways Maintenance Planning Decision-Support Platform**  
> AI & Operations Research Project | Multi-Departmental Optimization (Engineering, TRD, S&T)

---

## 📌 Executive Summary

**UnityTrack** is a decision-support and constraint-optimization platform for Indian Railways maintenance operations. It breaks departmental silos by combining work across:
1. **Engineering (Civil / Track)**: Track renewal, ballast tamping, rail weld repairs.
2. **Traction Distribution (TRD / Electrical)**: Catenary wire maintenance, 25 kV AC power cutoffs.
3. **Signal & Telecom (S&T)**: Points, track circuits, axle counters, signals.

By co-locating maintenance within unified block possessions and scheduling them between timetable train slots using **Google OR-Tools CP-SAT**, UnityTrack minimizes track possession requests and drastically reduces train delays.

---

## 🚀 Quickstart for Team Members (Run in 3 Minutes)

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**
- **Git**

### 1. Clone & Set Up Backend
```bash
# Clone the repository
git clone https://github.com/storm309/UnityTrack.git
cd UnityTrack/backend

# Create virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations & seed synthetic database (50 tasks across 3 departments)
python -m app.seed --seed 42 --reset

# Start the FastAPI backend server
python -m uvicorn app.main:app --app-dir . --host 0.0.0.0 --port 8000 --reload
```
Backend API will be live at:
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **Health Check:** `http://localhost:8000/health`

---

### 2. Set Up Frontend
Open a new terminal in the project root:
```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```
Frontend will be live at: **`http://localhost:3000`**

---

### 3. Verify System Health & Run Automated Tests
```bash
# In backend terminal:
pytest backend/tests -v               # All 82 tests must pass
ruff check backend                    # Code style check
mypy backend/app                      # Strict static type check

# In frontend terminal:
npm test                              # Vitest component tests (8 tests must pass)
npm run typecheck                     # TypeScript check (0 errors)
npm run lint                          # ESLint check (0 errors)
```

---

## 🗺️ Completed Milestones (Sections 0 through 5)

All the following core modules are completely built, integrated, and fully functional:

| Phase / Section | Core Backend Engine | Frontend Route | Status |
| :--- | :--- | :--- | :---: |
| **Section 0** | Monorepo structure, FastAPI server, Next.js app, CI workflow | [`/`](http://localhost:3000) (Dashboard & Health Contract) | ✅ Complete |
| **Section 1** | Corridor & Section models, Timetable train slots, Maintenance windows, Synthetic database generator | [`/corridors`](http://localhost:3000/corridors), [`/tasks`](http://localhost:3000/tasks) | ✅ Complete |
| **Section 2** | Multi-criteria priority engine ($w_1\text{Crit} + w_2\text{Sev} + w_3\text{Due} + w_4\text{Traf}$) | [`/priority`](http://localhost:3000/priority) (Live weights sliders) | ✅ Complete |
| **Section 3** | Cross-department compatibility matrix, Safety power-off rules, Candidate bundling engine | [`/bundles`](http://localhost:3000/bundles) (Pairwise validator) | ✅ Complete |
| **Section 4** | Google OR-Tools CP-SAT optimizer, Siloed baseline comparison, Validated schedule generation | [`/plans`](http://localhost:3000/plans) (Schedule & savings cards) | ✅ Complete |
| **Section 5** | What-if scenario simulator (Crew crunches, Traffic surges, Weather line closures, Defect injections) | [`/scenarios`](http://localhost:3000/scenarios) (Multi-scenario matrix) | ✅ Complete |
| **Section 6 (Backend)** | Deterministic explanation generator with strict anti-hallucination fact checking | `GET /api/plans/{id}/explanations` | ✅ Complete |

---

## 📋 Remaining Work & Task Assignments (Sections 6 to 10)

Any group member can pick up any of the following self-contained tasks:

---

### 🔹 Task 1: Complete Section 6 — Explanations UI & LLM Polish
- **Assigned To:** *Team Member 1*
- **Estimated Effort:** 2–3 hours
- **Objective:** Surface the deterministic explanation engine in the frontend UI.
- **Backend status:** Done! `GET /api/plans/{id}/explanations` is implemented and verified with 6 unit tests in `backend/tests/test_explanations.py`.
- **Steps to Complete:**
  1. Open `frontend/src/app/plans/page.tsx`.
  2. Add an **"Explain This Plan"** button or tab that calls `getPlanExplanations(planId)` from `@/lib/api-client`.
  3. Render an **Explanation Drawer / Panel** with 4 tabs:
     - **Recommendation Justification**: Human-readable narrative explaining why the optimizer saved $X$ blocks and $Y$ disruption minutes compared to the siloed departmental baseline.
     - **Bundle Explanations**: Why tasks are co-located (shared corridor section, compatible timetable window, power-off safety reuse).
     - **Priority Breakdowns**: Mathematical factor contribution bars for each scheduled task.
     - **Delay Binding Bottlenecks**: Binding constraints explanation (`RESOURCE_CREW_BOTTLENECK`, `ENGINEERING_SEQUENTIAL_CHAIN`, or `TIMETABLE_TRAFFIC_SATURATION`).
  4. *(Optional Bonus)*: Set `ENABLE_LLM_POLISHING=true` in `backend/app/config.py` and supply a `GEMINI_API_KEY` to test LLM narrative polishing.
- **Acceptance Criteria:**
  - Clicking any generated plan shows the complete explanation breakdown without errors.
  - `npm test` and `npm run typecheck` pass cleanly.

---

### 🔹 Task 2: Section 7 — Visual Gantt / Time-Space Diagram
- **Assigned To:** *Team Member 2*
- **Estimated Effort:** 3–4 hours
- **Objective:** Give train controllers a visual corridor maintenance Gantt timeline.
- **Steps to Complete:**
  1. In `frontend/src/app/plans/page.tsx` (or a dedicated component `frontend/src/components/GanttTimeline.tsx`):
     - Horizontal X-Axis: Time of day (0 to 1440 minutes, with 2-hour tick marks).
     - Vertical Y-Axis: Track sections along the corridor (`SEC-01` to `SEC-08`).
  2. Draw scheduled maintenance blocks as colored horizontal bars:
     - **Engineering:** Amber `#f59e0b`
     - **TRD:** Sky Blue `#0ea5e9`
     - **S&T:** Emerald `#10b981`
     - **Bundled Blocks:** Indigo gradient
  3. Overlay train timetable paths as diagonal lines passing through sections.
  4. Clicking on any block opens a popover showing task details, assigned crew gangs, and duration.
- **Acceptance Criteria:**
  - Clear visual distinction between train movements and maintenance blocks.
  - Responsive scrolling across the 7-day planning horizon.

---

### 🔹 Task 3: Section 8 — Emergency Interactive Replanning Wizard
- **Assigned To:** *Team Member 3*
- **Estimated Effort:** 3–4 hours
- **Objective:** Provide a fast incident-response tool when an emergency occurs during active operations.
- **Backend reference:** The scenario engine (`backend/app/optimizer/scenario.py` and `/api/scenarios/run`) already supports dynamic task injection and section closures without mutating historical data.
- **Steps to Complete:**
  1. Create an **"Emergency Incident Wizard"** modal in `/plans` or a dedicated route `/replan`:
     - Incident Type selector: Broken Rail / Ultrasonic Flaw, OHE Wire Breakdown, Signal Interlocking Failure, Flash Flood / Waterlogging.
     - Section location and emergency duration.
  2. When the user clicks "Re-optimize Corridor":
     - Pin all past and in-progress blocks (immutable history).
     - Call CP-SAT with a fast 5-second timeout to fit the emergency block and reschedule delayed lower-priority tasks.
  3. Present a differential comparison: "2 tasks pushed back, 0 safety violations, +45 min net delay".
- **Acceptance Criteria:**
  - Fast response time (<5 seconds).
  - Clear before/after comparison view for the train controller.

---

### 🔹 Task 4: Section 9 — Benchmarks, Scalability & Performance Validation
- **Assigned To:** *Team Member 4*
- **Estimated Effort:** 2–3 hours
- **Objective:** Prove that UnityTrack scales to real Indian Railways divisional scale.
- **Steps to Complete:**
  1. Create a benchmark script `backend/benchmarks/benchmark_optimizer.py`.
  2. Test CP-SAT solve times and memory across 3 workload tiers:
     - Tier 1: Small (20 tasks, 4 sections, 3-day horizon)
     - Tier 2: Medium (50 tasks, 8 sections, 7-day horizon — default)
     - Tier 3: Divisional Scale (150+ tasks, 16 sections, 14-day horizon)
  3. Record metrics: Solve Time (seconds), Number of Variables, Number of Constraints, Disruption Reduction (%).
  4. Output a clean Markdown table and summary chart in `docs/BENCHMARKS.md`.
- **Acceptance Criteria:**
  - Optimizer achieves FEASIBLE or OPTIMAL state within 30 seconds for Tier 2 and Tier 3.
  - Zero hard constraint violations confirmed by independent validator.

---

### 🔹 Task 5: Section 10 — Packaging, Deployment & Presentation Demo
- **Assigned To:** *Team Member 5 / Project Lead*
- **Estimated Effort:** 2–3 hours
- **Objective:** Ensure single-command Docker deployment and prepare the final project submission.
- **Steps to Complete:**
  1. Verify `docker compose up --build` works out of the box on a clean machine.
  2. Prepare a 5-minute live demonstration script covering:
     - Departmental silos problem statement.
     - Priority scoring with custom weight sliders.
     - Automated cross-departmental bundling.
     - CP-SAT optimal schedule vs siloed baseline metrics.
     - Live What-If disruption simulation (crew crunch / monsoon line closure).
  3. Create presentation slides in `docs/presentation/` summarizing architecture, algorithms, and quantitative results.
- **Acceptance Criteria:**
  - Single command `docker compose up` starts PostgreSQL, FastAPI, and Next.js seamlessly.
  - Clear presentation materials ready for evaluation.

---

## 🛠️ Monorepo Rules & Conventions

To ensure zero merge conflicts and continuous quality, please follow these guidelines:

1. **Strict Type Safety**: Never manually edit `frontend/src/lib/api-types.ts`. If backend schemas change, run:
   ```bash
   python backend/export_openapi.py
   npm --prefix frontend run gen:api
   ```
2. **Optimizer Decoupling**: Keep all optimizer logic in `backend/app/optimizer/` 100% pure Python. Never import FastAPI or SQLAlchemy inside optimizer files.
3. **Always Run Checks Before Committing**:
   ```bash
   # Backend:
   pytest backend/tests
   ruff check backend
   mypy backend/app

   # Frontend:
   npm --prefix frontend test
   npm --prefix frontend run typecheck
   npm --prefix frontend run lint
   ```
4. **Git Branching Strategy**:
   - Create a feature branch: `git checkout -b feature/task-X-short-description`
   - Keep commit messages concise: `feat(plans): add explanation drawer for Section 6`
   - Test and merge into `main`.
