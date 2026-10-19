"use client";

import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api-client";
import { Activity, CheckCircle2, AlertTriangle, RefreshCw, Train, Shield, Wrench, Zap } from "lucide-react";

export default function HomePage() {
  const { data, error, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10000,
  });

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 md:p-12">
      <div className="w-full max-w-4xl space-y-8">
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
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
      </div>
    </main>
  );
}
