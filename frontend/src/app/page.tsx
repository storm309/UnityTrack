"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  getHealth,
  getCorridors,
  getTasks,
  getCandidateBundles,
  getPlans,
  getScenarios,
} from "@/lib/api-client";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Train,
  Shield,
  Wrench,
  Zap,
  ArrowRight,
  Layers,
  Sliders,
  Calendar,
  GitBranch,
} from "lucide-react";

export default function HomePage() {
  const { data, error, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10000,
  });

  const { data: corridors } = useQuery({
    queryKey: ["corridors"],
    queryFn: () => getCorridors(),
  });

  const { data: tasks } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => getTasks(),
  });

  const { data: bundles } = useQuery({
    queryKey: ["bundles"],
    queryFn: () => getCandidateBundles(),
  });

  const { data: plans } = useQuery({
    queryKey: ["plans"],
    queryFn: () => getPlans(),
  });

  const { data: scenarios } = useQuery({
    queryKey: ["scenarios"],
    queryFn: () => getScenarios(),
  });

  const engTasksCount = tasks?.filter((t) => t.department === "ENGINEERING").length ?? 0;
  const trdTasksCount = tasks?.filter((t) => t.department === "TRD").length ?? 0;
  const sntTasksCount = tasks?.filter((t) => t.department === "SNT").length ?? 0;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div className="flex items-center space-x-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
            <Train className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-2">
              UnityTrack
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Section 0
              </span>
            </h1>
            <p className="text-sm text-slate-400">
              Decision-Support Platform for Indian Railways Maintenance Planning
            </p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          Refresh Status
        </button>
      </div>

      {/* System Health Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl backdrop-blur">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
            <Activity className="h-5 w-5 text-emerald-400" />
            Backend Connection & Health Contract
          </h2>
          <div className="text-xs text-slate-500 font-mono">
            Endpoint: GET /health
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-3 py-6 text-slate-400">
            <RefreshCw className="h-5 w-5 animate-spin text-blue-400" />
            <span>Checking backend API status via generated OpenAPI client...</span>
          </div>
        ) : error ? (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-4 text-rose-300 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Backend Unreachable or Health Check Failed</p>
              <p className="text-sm text-rose-300/80 mt-1">{(error as Error).message}</p>
              <p className="text-xs text-slate-400 mt-2">
                Verify backend service is running on <code>http://localhost:8000</code>.
              </p>
            </div>
          </div>
        ) : data ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
              <span className="text-xs font-medium text-slate-400">API Status</span>
              <div className="mt-2 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                <span className="font-bold text-slate-100 uppercase text-sm tracking-wide">
                  {data.status}
                </span>
              </div>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
              <span className="text-xs font-medium text-slate-400">Database</span>
              <div className="mt-2 flex items-center gap-2">
                {data.database === "healthy" ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-amber-400" />
                )}
                <span className="font-bold text-slate-100 capitalize text-sm">
                  {data.database}
                </span>
              </div>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
              <span className="text-xs font-medium text-slate-400">Environment</span>
              <div className="mt-2 text-sm font-semibold text-slate-200">
                {data.environment}
              </div>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
              <span className="text-xs font-medium text-slate-400">API Version</span>
              <div className="mt-2 text-sm font-semibold text-slate-200 font-mono">
                v{data.version}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Cross-Department Operational Metrics Summary (Sections 1-5) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Corridors Active</span>
            <Train className="h-4 w-4 text-blue-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{corridors?.length ?? 1}</div>
          <p className="mt-1 text-[11px] text-slate-400">High-density routes configured</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Pending Tasks</span>
            <Wrench className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{tasks?.length ?? 0}</div>
          <p className="mt-1 text-[11px] text-slate-400">
            ENG: {engTasksCount} | TRD: {trdTasksCount} | SNT: {sntTasksCount}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Bundles Formed</span>
            <Layers className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{bundles?.total_candidates ?? 0}</div>
          <p className="mt-1 text-[11px] text-slate-400">Cross-department co-locations</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Optimizer Plans</span>
            <Calendar className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{plans?.total_plans ?? 0}</div>
          <p className="mt-1 text-[11px] text-slate-400">{scenarios?.length ?? 0} What-If scenarios</p>
        </div>
      </div>

      {/* Unified Platform Modules (Sections 1 through 5) */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Operations & Intelligence Modules</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Link
            href="/corridors"
            className="group rounded-xl border border-slate-800 bg-slate-900/40 p-5 hover:border-blue-500/50 hover:bg-slate-900/70 transition"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-blue-600/15 text-blue-400 border border-blue-500/20 group-hover:bg-blue-600/25 transition">
                <Train className="h-5 w-5" />
              </div>
              <span className="text-xs font-mono text-slate-500">Section 1</span>
            </div>
            <h3 className="font-semibold text-slate-100 flex items-center gap-1.5 group-hover:text-blue-400 transition">
              Corridors & Timetables
              <ArrowRight className="h-4 w-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition" />
            </h3>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed">
              Explore track sections, electrified lines, maintenance windows, and timetable train slots.
            </p>
          </Link>

          <Link
            href="/tasks"
            className="group rounded-xl border border-slate-800 bg-slate-900/40 p-5 hover:border-amber-500/50 hover:bg-slate-900/70 transition"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-amber-600/15 text-amber-400 border border-amber-500/20 group-hover:bg-amber-600/25 transition">
                <Wrench className="h-5 w-5" />
              </div>
              <span className="text-xs font-mono text-slate-500">Section 1</span>
            </div>
            <h3 className="font-semibold text-slate-100 flex items-center gap-1.5 group-hover:text-amber-400 transition">
              Maintenance Task Register
              <ArrowRight className="h-4 w-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition" />
            </h3>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed">
              Unified cross-departmental task register for Engineering, TRD, and S&T maintenance items.
            </p>
          </Link>

          <Link
            href="/priority"
            className="group rounded-xl border border-slate-800 bg-slate-900/40 p-5 hover:border-purple-500/50 hover:bg-slate-900/70 transition"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-purple-600/15 text-purple-400 border border-purple-500/20 group-hover:bg-purple-600/25 transition">
                <Sliders className="h-5 w-5" />
              </div>
              <span className="text-xs font-mono text-slate-500">Section 2</span>
            </div>
            <h3 className="font-semibold text-slate-100 flex items-center gap-1.5 group-hover:text-purple-400 transition">
              Priority Scoring Engine
              <ArrowRight className="h-4 w-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition" />
            </h3>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed">
              Interactive weight tuning for Criticality, Defect Severity, Overdue Ratio, and Traffic Impact.
            </p>
          </Link>

          <Link
            href="/bundles"
            className="group rounded-xl border border-slate-800 bg-slate-900/40 p-5 hover:border-indigo-500/50 hover:bg-slate-900/70 transition"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-indigo-600/15 text-indigo-400 border border-indigo-500/20 group-hover:bg-indigo-600/25 transition">
                <Layers className="h-5 w-5" />
              </div>
              <span className="text-xs font-mono text-slate-500">Section 3</span>
            </div>
            <h3 className="font-semibold text-slate-100 flex items-center gap-1.5 group-hover:text-indigo-400 transition">
              Task Bundling & Compatibility
              <ArrowRight className="h-4 w-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition" />
            </h3>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed">
              Cross-department bundling studio & interactive pairwise task compatibility testing matrix.
            </p>
          </Link>

          <Link
            href="/plans"
            className="group rounded-xl border border-slate-800 bg-slate-900/40 p-5 hover:border-emerald-500/50 hover:bg-slate-900/70 transition"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-emerald-600/15 text-emerald-400 border border-emerald-500/20 group-hover:bg-emerald-600/25 transition">
                <Calendar className="h-5 w-5" />
              </div>
              <span className="text-xs font-mono text-slate-500">Section 4</span>
            </div>
            <h3 className="font-semibold text-slate-100 flex items-center gap-1.5 group-hover:text-emerald-400 transition">
              Constraint Optimizer Plans
              <ArrowRight className="h-4 w-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition" />
            </h3>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed">
              Google OR-Tools CP-SAT scheduling engine with scheduled block breakdown & silo baseline deltas.
            </p>
          </Link>

          <Link
            href="/scenarios"
            className="group rounded-xl border border-slate-800 bg-slate-900/40 p-5 hover:border-cyan-500/50 hover:bg-slate-900/70 transition"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-lg bg-cyan-600/15 text-cyan-400 border border-cyan-500/20 group-hover:bg-cyan-600/25 transition">
                <GitBranch className="h-5 w-5" />
              </div>
              <span className="text-xs font-mono text-slate-500">Section 5</span>
            </div>
            <h3 className="font-semibold text-slate-100 flex items-center gap-1.5 group-hover:text-cyan-400 transition">
              What-If Scenario Simulator
              <ArrowRight className="h-4 w-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition" />
            </h3>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed">
              Multi-scenario comparison matrix: adjust crew bottlenecks, traffic surges, and weather delays.
            </p>
          </Link>
        </div>
      </div>

      {/* Railway Maintenance Departments Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Wrench className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-slate-200">Engineering (ENG)</h3>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Track renewal, deep screening, tamping, weld repairs. Requires exclusive track block.
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Zap className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-slate-200">Traction (TRD)</h3>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            OHE maintenance, contact wire replacement, insulator washing. Requires power block.
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Shield className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-slate-200">Signal & Telecom (SNT)</h3>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Point machines, track circuits, axle counters, signals. Frequently co-locatable with TRD.
          </p>
        </div>
      </div>

      {/* Footer info */}
      <div className="text-center text-xs text-slate-500">
        UnityTrack Monorepo: FastAPI + CP-SAT Optimizer • Next.js App Router • Strict OpenAPI Contract
      </div>
    </main>
  );
}
