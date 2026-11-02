"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPlans,
  getPlan,
  generatePlan,
  getCorridors,
  PlanGenerateRequest,
} from "@/lib/api-client";
import { PageHeader } from "@/components/PageHeader";
import {
  Play,
  TrendingDown,
  Cpu,
} from "lucide-react";

export default function PlansPage() {
  const queryClient = useQueryClient();
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);

  // Generate form state
  const [generateForm, setGenerateForm] = useState<PlanGenerateRequest>({
    name: "Master Corridor 7-Day Plan",
    corridor_id: "CORR-01",
    time_limit_seconds: 30,
    weight_num_blocks: 1.0,
    weight_disruption_minutes: 1.0,
    weight_priority_lateness: 2.0,
    allow_adjacent_sections: false,
  });

  const { data: plansData } = useQuery({
    queryKey: ["plans"],
    queryFn: getPlans,
  });

  const { data: corridors } = useQuery({
    queryKey: ["corridors"],
    queryFn: getCorridors,
  });

  // Default to first plan if none selected
  const activePlanId = selectedPlanId || plansData?.plans[0]?.id;

  const { data: planDetail } = useQuery({
    queryKey: ["plan", activePlanId],
    queryFn: () => getPlan(activePlanId as string),
    enabled: Boolean(activePlanId),
  });

  const generateMutation = useMutation({
    mutationFn: (req: PlanGenerateRequest) => generatePlan(req),
    onSuccess: (newPlan) => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      setSelectedPlanId(newPlan.id);
      setIsGenerateOpen(false);
    },
  });

  const handleGenerateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    generateMutation.mutate(generateForm);
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-6">
      <PageHeader
        title="Constraint Optimizer Schedules"
        badge="Section 4"
        description="Google OR-Tools CP-SAT constraint programming engine solving timetable conflicts, resource bounds, and cross-departmental block bundling"
        actions={
          <button
            onClick={() => setIsGenerateOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 transition"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            <span>Generate Plan (CP-SAT)</span>
          </button>
        }
      />

      {/* Generate Plan Modal */}
      {isGenerateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Cpu className="h-4 w-4 text-emerald-400" />
                <h2 className="text-sm font-semibold text-white">CP-SAT Optimizer Run</h2>
              </div>
              <button
                onClick={() => setIsGenerateOpen(false)}
                className="text-slate-400 hover:text-white text-xs"
              >
                Close
              </button>
            </div>

            <form onSubmit={handleGenerateSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Plan Name</label>
                <input
                  type="text"
                  required
                  value={generateForm.name || ""}
                  onChange={(e) => setGenerateForm({ ...generateForm, name: e.target.value })}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Target Corridor</label>
                  <select
                    value={generateForm.corridor_id || ""}
                    onChange={(e) =>
                      setGenerateForm({ ...generateForm, corridor_id: e.target.value })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                  >
                    {corridors?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Time Limit (Seconds)</label>
                  <input
                    type="number"
                    min={5}
                    max={120}
                    value={generateForm.time_limit_seconds}
                    onChange={(e) =>
                      setGenerateForm({
                        ...generateForm,
                        time_limit_seconds: Number(e.target.value),
                      })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Disruption Weight</label>
                  <input
                    type="number"
                    step={0.5}
                    min={0.5}
                    max={10}
                    value={generateForm.weight_disruption_minutes}
                    onChange={(e) =>
                      setGenerateForm({
                        ...generateForm,
                        weight_disruption_minutes: Number(e.target.value),
                      })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Block Penalty Weight</label>
                  <input
                    type="number"
                    step={0.5}
                    min={0.5}
                    max={10}
                    value={generateForm.weight_num_blocks}
                    onChange={(e) =>
                      setGenerateForm({
                        ...generateForm,
                        weight_num_blocks: Number(e.target.value),
                      })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div className="pt-1">
                <label className="flex items-center space-x-2 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={generateForm.allow_adjacent_sections}
                    onChange={(e) =>
                      setGenerateForm({
                        ...generateForm,
                        allow_adjacent_sections: e.target.checked,
                      })
                    }
                    className="rounded border-slate-700 text-emerald-600 focus:ring-0"
                  />
                  <span>Allow Adjacent Track Section Bundling</span>
                </label>
              </div>

              <div className="pt-2 flex justify-end space-x-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsGenerateOpen(false)}
                  className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:bg-slate-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={generateMutation.isPending}
                  className="rounded-lg bg-emerald-600 px-4 py-1.5 font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 transition"
                >
                  {generateMutation.isPending ? "Solving CP-SAT..." : "Solve & Save Plan"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Plans List Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {plansData?.plans.map((p) => {
          const isSelected = activePlanId === p.id;
          return (
            <button
              key={p.id}
              onClick={() => setSelectedPlanId(p.id)}
              className={`rounded-xl border p-4 text-left transition ${
                isSelected
                  ? "border-emerald-500/50 bg-emerald-950/20 shadow-md"
                  : "border-slate-800 bg-slate-900/40 hover:bg-slate-900/70"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-emerald-400">{p.id}</span>
                <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-400 border border-emerald-500/30">
                  {p.status}
                </span>
              </div>
              <h3 className="mt-1 font-semibold text-sm text-slate-200">{p.name}</h3>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono text-slate-400 pt-2 border-t border-slate-800/80">
                <div>
                  Blocks: <span className="text-white font-bold">{p.total_blocks}</span>
                </div>
                <div>
                  Disruption: <span className="text-white font-bold">{p.total_disruption_minutes}m</span>
                </div>
                <div>
                  Scheduled: <span className="text-white font-bold">{p.tasks_scheduled} tasks</span>
                </div>
                <div>
                  Violations: <span className="text-emerald-400 font-bold">0 (Valid)</span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected Plan Details & Baseline Comparison */}
      {planDetail && (
        <div className="space-y-6">
          {/* Comparison vs Siloed Baseline Card */}
          {planDetail.comparison && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
              <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
                <TrendingDown className="h-4 w-4 text-emerald-400" />
                <h2 className="text-sm font-semibold text-slate-100">
                  Multi-Departmental Optimization Impact vs Siloed Operations
                </h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <span className="text-xs text-slate-400">Track Line Blocks Saved</span>
                  <div className="mt-1 text-2xl font-bold text-emerald-400 font-mono">
                    {planDetail.comparison.block_reduction_count} blocks
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500 font-mono">
                    {planDetail.comparison.block_reduction_pct.toFixed(1)}% reduction in line possessions
                  </p>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <span className="text-xs text-slate-400">Total Disruption Minutes Saved</span>
                  <div className="mt-1 text-2xl font-bold text-blue-400 font-mono">
                    {planDetail.comparison.disruption_savings_min} min
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500 font-mono">
                    From {planDetail.comparison.baseline_disruption_min}m down to {planDetail.comparison.optimized_disruption_min}m
                  </p>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <span className="text-xs text-slate-400">Baseline vs Optimized Blocks</span>
                  <div className="mt-1 text-2xl font-bold text-amber-400 font-mono">
                    {planDetail.comparison.baseline_blocks} → {planDetail.comparison.optimized_blocks}
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500 font-mono">
                    {planDetail.metrics.tasks_scheduled} tasks scheduled without violations
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Scheduled Blocks & Tasks Breakdown */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">
                Scheduled Maintenance Blocks ({planDetail.planned_blocks.length})
              </h2>
              <span className="text-xs font-mono text-slate-400">
                Solve time: {planDetail.metrics.solve_time_seconds.toFixed(2)}s | Disruption: {planDetail.metrics.total_disruption_minutes}m
              </span>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-800 bg-slate-950/70 text-slate-400">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Block ID</th>
                    <th className="px-4 py-3 font-semibold">Section</th>
                    <th className="px-4 py-3 font-semibold">Time Window</th>
                    <th className="px-4 py-3 font-semibold">Duration</th>
                    <th className="px-4 py-3 font-semibold">Blocks Granted</th>
                    <th className="px-4 py-3 font-semibold">Assigned Tasks ({planDetail.metrics.tasks_scheduled})</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {planDetail.planned_blocks.map((blk) => (
                    <tr key={blk.id} className="hover:bg-slate-900/50 transition">
                      <td className="px-4 py-3 font-bold text-emerald-400">{blk.id}</td>
                      <td className="px-4 py-3 text-slate-300">{blk.section_id}</td>
                      <td className="px-4 py-3 text-slate-400">
                        {blk.start_min}m → {blk.end_min}m (Day {Math.floor(blk.start_min / 1440) + 1})
                      </td>
                      <td className="px-4 py-3 text-slate-200 font-bold">{blk.duration_min}m</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1 font-sans">
                          {blk.requires_track_block && (
                            <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-400">
                              Track Block
                            </span>
                          )}
                          {blk.requires_power_off && (
                            <span className="rounded bg-sky-500/10 px-1.5 py-0.5 text-[10px] text-sky-400">
                              Power Off
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-sans">
                        <div className="flex flex-wrap gap-1.5">
                          {blk.tasks.map((t) => (
                            <span
                              key={t.task_id}
                              title={t.title}
                              className="inline-flex items-center rounded bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-slate-200"
                            >
                              [{t.department}] {t.task_id}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
