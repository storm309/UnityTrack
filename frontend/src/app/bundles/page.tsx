"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getCandidateBundles,
  checkTasksCompatibility,
  getTasks,
  getSections,
  PairwiseCompatibilityResponse,
} from "@/lib/api-client";
import { PageHeader } from "@/components/PageHeader";
import {
  CheckCircle2,
  AlertTriangle,
  Sparkles,
} from "lucide-react";

export default function BundlesPage() {
  const [crossDeptOnly, setCrossDeptOnly] = useState(true);
  const [allowAdjacent, setAllowAdjacent] = useState(false);
  const [selectedSection, setSelectedSection] = useState("");

  // Pairwise Checker state
  const [taskAId, setTaskAId] = useState("");
  const [taskBId, setTaskBId] = useState("");
  const [pairResult, setPairResult] = useState<PairwiseCompatibilityResponse | null>(null);
  const [isCheckingPair, setIsCheckingPair] = useState(false);
  const [pairError, setPairError] = useState<string | null>(null);

  const { data: bundlesData, isLoading } = useQuery({
    queryKey: ["bundles", crossDeptOnly, allowAdjacent, selectedSection],
    queryFn: () =>
      getCandidateBundles({
        crossDepartmentOnly: crossDeptOnly,
        allowAdjacentSections: allowAdjacent,
        sectionId: selectedSection || undefined,
      }),
  });

  const { data: tasks } = useQuery({
    queryKey: ["all-tasks"],
    queryFn: () => getTasks(),
  });

  const { data: sections } = useQuery({
    queryKey: ["sections"],
    queryFn: () => getSections(),
  });

  const handleCheckPairwise = async () => {
    if (!taskAId || !taskBId) {
      setPairError("Please select both Task A and Task B");
      return;
    }
    if (taskAId === taskBId) {
      setPairError("Task A and Task B must be different tasks");
      return;
    }
    setIsCheckingPair(true);
    setPairError(null);
    try {
      const res = await checkTasksCompatibility({
        taskAId,
        taskBId,
        allowAdjacentSections: allowAdjacent,
      });
      setPairResult(res);
    } catch (err: unknown) {
      setPairError((err as Error).message);
    } finally {
      setIsCheckingPair(false);
    }
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-6">
      <PageHeader
        title="Cross-Departmental Task Bundling"
        badge="Section 3"
        description="Synchronize Engineering line blocks, TRD power cutoffs, and S&T signaling works into unified co-located maintenance windows"
      />

      {/* Interactive Pairwise Compatibility Checker */}
      <div className="rounded-xl border border-blue-500/30 bg-blue-950/20 p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-blue-500/20 pb-3">
          <div className="flex items-center space-x-2">
            <Sparkles className="h-4 w-4 text-blue-400" />
            <h2 className="text-sm font-semibold text-white">
              Pairwise Compatibility Validator
            </h2>
          </div>
          <span className="text-[11px] text-blue-300 font-mono">
            Safety & Spatial Bundling Engine
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Task A (Primary Track or Power Block)
            </label>
            <select
              value={taskAId}
              onChange={(e) => {
                setTaskAId(e.target.value);
                setPairResult(null);
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">-- Select Task A --</option>
              {tasks?.map((t) => (
                <option key={t.id} value={t.id}>
                  [{t.department}] {t.id} - {t.title.slice(0, 45)} ({t.section_id})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Task B (Candidate Co-Located Work)
            </label>
            <select
              value={taskBId}
              onChange={(e) => {
                setTaskBId(e.target.value);
                setPairResult(null);
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">-- Select Task B --</option>
              {tasks?.map((t) => (
                <option key={t.id} value={t.id}>
                  [{t.department}] {t.id} - {t.title.slice(0, 45)} ({t.section_id})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <label className="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={allowAdjacent}
              onChange={(e) => setAllowAdjacent(e.target.checked)}
              className="rounded border-slate-700 text-blue-600 focus:ring-0"
            />
            <span>Allow spatial bundling across adjacent track sections</span>
          </label>

          <button
            onClick={handleCheckPairwise}
            disabled={isCheckingPair || !taskAId || !taskBId}
            className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50 transition"
          >
            {isCheckingPair ? "Validating Rules..." : "Check Compatibility"}
          </button>
        </div>

        {pairError && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-3 text-xs text-rose-300">
            {pairError}
          </div>
        )}

        {/* Pairwise Result Card */}
        {pairResult && (
          <div
            className={`rounded-xl border p-4 text-xs space-y-2.5 transition ${
              pairResult.is_compatible
                ? "border-emerald-500/40 bg-emerald-950/20 text-emerald-200"
                : "border-rose-500/40 bg-rose-950/20 text-rose-200"
            }`}
          >
            <div className="flex items-center justify-between font-bold">
              <div className="flex items-center space-x-2">
                {pairResult.is_compatible ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-rose-400" />
                )}
                <span className="text-sm">
                  {pairResult.is_compatible
                    ? "Compatible for Unified Bundling"
                    : "Incompatible Tasks"}
                </span>
              </div>
              <span className="font-mono text-[11px] uppercase tracking-wider">
                Execution: {pairResult.execution_mode}
              </span>
            </div>

            <div className="space-y-1">
              {pairResult.conflict_reason && (
                <p className="text-rose-300 font-medium">Conflict: {pairResult.conflict_reason}</p>
              )}
              {pairResult.reasons.map((r, i) => (
                <p key={i} className="text-slate-300 leading-relaxed">• {r}</p>
              ))}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 font-mono text-[11px]">
              <div>
                <span className="text-slate-400">Duration:</span>{" "}
                <span className="font-bold text-white">
                  {pairResult.combined_duration_min} min
                </span>
              </div>
              <div>
                <span className="text-slate-400">Savings:</span>{" "}
                <span className="font-bold text-emerald-400">
                  {pairResult.disruption_savings_min} min saved
                </span>
              </div>
              <div>
                <span className="text-slate-400">Track Block:</span>{" "}
                <span className="font-bold text-white">
                  {pairResult.requires_track_block ? "REQUIRED" : "NOT NEEDED"}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Power Off:</span>{" "}
                <span className="font-bold text-white">
                  {pairResult.requires_power_off ? "REQUIRED" : "NOT NEEDED"}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Candidate Bundles Filter bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-semibold text-slate-400">Filter Bundles:</span>

          <button
            onClick={() => setCrossDeptOnly(!crossDeptOnly)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              crossDeptOnly
                ? "bg-indigo-600 text-white"
                : "bg-slate-950 text-slate-400 border border-slate-800"
            }`}
          >
            Cross-Department Only
          </button>

          <select
            value={selectedSection}
            onChange={(e) => setSelectedSection(e.target.value)}
            className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
          >
            <option value="">All Track Sections</option>
            {sections?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} ({s.name})
              </option>
            ))}
          </select>
        </div>

        <div className="text-xs text-slate-400 font-mono">
          Total Candidate Bundles:{" "}
          <span className="font-bold text-white">{bundlesData?.total_candidates ?? 0}</span>
        </div>
      </div>

      {/* Candidate Bundles Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          <div className="col-span-full py-12 text-center text-slate-400">
            Scanning cross-departmental compatibility rules...
          </div>
        ) : bundlesData?.candidates && bundlesData.candidates.length > 0 ? (
          bundlesData.candidates.map((bundle) => {
            return (
              <div
                key={bundle.bundle_id}
                className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-3 hover:border-slate-700 transition"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-indigo-400">
                    {bundle.bundle_id}
                  </span>
                  <div className="flex items-center space-x-1">
                    {bundle.departments.map((dept) => (
                      <span
                        key={dept}
                        className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                          dept === "ENGINEERING"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : dept === "TRD"
                            ? "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                            : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        }`}
                      >
                        {dept === "ENGINEERING" ? "ENG" : dept}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="text-xs text-slate-300">
                  <span className="text-slate-500">Section: </span>
                  <span className="font-mono font-medium text-white">{bundle.section_id}</span>
                </div>

                {/* Tasks in Bundle */}
                <div className="space-y-1 rounded-lg bg-slate-950/60 p-2.5 text-[11px]">
                  <div className="text-slate-500 font-semibold text-[10px] uppercase">
                    Tasks Co-Located ({bundle.task_ids.length}):
                  </div>
                  {bundle.tasks_summary.map((t) => (
                    <div key={t.id} className="flex items-center justify-between text-slate-300">
                      <span className="truncate max-w-[200px]" title={t.title}>
                        {t.id}: {t.title}
                      </span>
                      <span className="font-mono text-slate-400">{t.duration_min}m</span>
                    </div>
                  ))}
                </div>

                {/* Efficiency metrics */}
                <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Duration: {bundle.duration_min}m</span>
                  {bundle.disruption_savings_min > 0 && (
                    <span className="text-emerald-400 font-bold">
                      +{bundle.disruption_savings_min}m saved ({bundle.efficiency_gain_pct.toFixed(0)}%)
                    </span>
                  )}
                </div>
              </div>
            );
          })
        ) : (
          <div className="col-span-full py-12 text-center text-slate-500">
            No candidate bundles found for active filters.
          </div>
        )}
      </div>
    </main>
  );
}
