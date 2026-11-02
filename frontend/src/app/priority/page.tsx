"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPriorityRanking } from "@/lib/api-client";
import { PageHeader } from "@/components/PageHeader";
import {
  Sliders,
  RotateCcw,
} from "lucide-react";

export default function PriorityPage() {
  // Slider states (must sum to 1.0)
  const [wCrit, setWCrit] = useState<number>(0.35);
  const [wSev, setWSev] = useState<number>(0.25);
  const [wDue, setWDue] = useState<number>(0.25);
  const [wTraf, setWTraf] = useState<number>(0.15);

  const [selectedDept, setSelectedDept] = useState<string>("");
  const [selectedBand, setSelectedBand] = useState<string>("");

  const weightSum = Number((wCrit + wSev + wDue + wTraf).toFixed(3));
  const isWeightsValid = Math.abs(weightSum - 1.0) < 0.001;

  const { data: rankingData, isLoading, isFetching } = useQuery({
    queryKey: [
      "priority-ranking",
      wCrit,
      wSev,
      wDue,
      wTraf,
      selectedDept,
      selectedBand,
    ],
    queryFn: () =>
      getPriorityRanking({
        weightCriticality: wCrit,
        weightSeverity: wSev,
        weightOverdue: wDue,
        weightTraffic: wTraf,
        department: selectedDept || undefined,
        priorityBand: selectedBand || undefined,
      }),
    enabled: isWeightsValid,
  });

  const handleNormalize = () => {
    if (weightSum <= 0) return;
    setWCrit(Number((wCrit / weightSum).toFixed(2)));
    setWSev(Number((wSev / weightSum).toFixed(2)));
    setWDue(Number((wDue / weightSum).toFixed(2)));
    setWTraf(Number((1.0 - (wCrit / weightSum) - (wSev / weightSum) - (wDue / weightSum)).toFixed(2)));
  };

  const handleResetDefaults = () => {
    setWCrit(0.35);
    setWSev(0.25);
    setWDue(0.25);
    setWTraf(0.15);
  };

  const getBandBadge = (band: string) => {
    switch (band) {
      case "CRITICAL":
        return (
          <span className="rounded bg-rose-500/15 px-2 py-0.5 text-[10px] font-bold text-rose-400 border border-rose-500/30">
            CRITICAL (80-100)
          </span>
        );
      case "HIGH":
        return (
          <span className="rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold text-amber-400 border border-amber-500/30">
            HIGH (60-79)
          </span>
        );
      case "MEDIUM":
        return (
          <span className="rounded bg-blue-500/15 px-2 py-0.5 text-[10px] font-bold text-blue-400 border border-blue-500/30">
            MEDIUM (40-59)
          </span>
        );
      case "LOW":
        return (
          <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-bold text-slate-400">
            LOW (&lt;40)
          </span>
        );
      default:
        return <span>{band}</span>;
    }
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-6">
      <PageHeader
        title="Multi-Criteria Priority Scoring"
        badge="Section 2"
        description="Explainable 0-100 priority index calculating urgency across Engineering, TRD, and S&T tasks with mathematical factor traceability"
        actions={
          <button
            onClick={handleResetDefaults}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800 transition"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset IR Defaults</span>
          </button>
        }
      />

      {/* Interactive Weights Workbench */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Sliders className="h-4 w-4 text-purple-400" />
            <h2 className="text-sm font-semibold text-slate-100">
              Interactive Objective Weights Tuning
            </h2>
          </div>
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400">Sum of Weights:</span>
            <span
              className={`font-mono font-bold ${
                isWeightsValid ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {weightSum.toFixed(2)} / 1.00
            </span>
            {!isWeightsValid && (
              <button
                onClick={handleNormalize}
                className="rounded bg-rose-500/20 px-2 py-0.5 text-[11px] font-semibold text-rose-300 hover:bg-rose-500/30"
              >
                Auto-Normalize
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Criticality */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-300">Track Criticality</span>
              <span className="font-mono text-purple-400 font-bold">{(wCrit * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min={0.05}
              max={0.7}
              step={0.05}
              value={wCrit}
              onChange={(e) => setWCrit(Number(e.target.value))}
              className="w-full accent-purple-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">Asset speed, route density rating</p>
          </div>

          {/* Defect Severity */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-300">Defect Severity</span>
              <span className="font-mono text-amber-400 font-bold">{(wSev * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min={0.05}
              max={0.7}
              step={0.05}
              value={wSev}
              onChange={(e) => setWSev(Number(e.target.value))}
              className="w-full accent-amber-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">Ultrasonic cracks, OHE sag severity</p>
          </div>

          {/* Overdue Ratio */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-300">Overdue Ratio</span>
              <span className="font-mono text-rose-400 font-bold">{(wDue * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min={0.05}
              max={0.7}
              step={0.05}
              value={wDue}
              onChange={(e) => setWDue(Number(e.target.value))}
              className="w-full accent-rose-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">Time elapsed past target schedule</p>
          </div>

          {/* Traffic Impact */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-300">Traffic Impact</span>
              <span className="font-mono text-blue-400 font-bold">{(wTraf * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min={0.05}
              max={0.7}
              step={0.05}
              value={wTraf}
              onChange={(e) => setWTraf(Number(e.target.value))}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">Passenger & freight delay risk</p>
          </div>
        </div>
      </div>

      {/* Filter and Summary Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-400 font-medium">Department:</span>
          {["", "ENGINEERING", "TRD", "SNT"].map((dept) => (
            <button
              key={dept}
              onClick={() => setSelectedDept(dept)}
              className={`rounded-lg px-2.5 py-1 transition ${
                selectedDept === dept
                  ? "bg-purple-600 text-white font-semibold"
                  : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              {dept === "" ? "All" : dept}
            </button>
          ))}
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-400 font-medium">Priority Band:</span>
          {["", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((band) => (
            <button
              key={band}
              onClick={() => setSelectedBand(band)}
              className={`rounded-lg px-2.5 py-1 transition ${
                selectedBand === band
                  ? "bg-purple-600 text-white font-semibold"
                  : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              {band === "" ? "All" : band}
            </button>
          ))}
        </div>
      </div>

      {/* Ranked Tasks Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-800 bg-slate-950/70 text-slate-400">
            <tr>
              <th className="px-4 py-3 font-semibold">Rank</th>
              <th className="px-4 py-3 font-semibold">Task ID & Description</th>
              <th className="px-4 py-3 font-semibold">Department</th>
              <th className="px-4 py-3 font-semibold">Section</th>
              <th className="px-4 py-3 font-semibold">Score (0-100)</th>
              <th className="px-4 py-3 font-semibold">Band</th>
              <th className="px-4 py-3 font-semibold min-w-[200px]">Factor Contributions Breakdown</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {isLoading || isFetching ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  Calculating real-time priority scores...
                </td>
              </tr>
            ) : rankingData?.tasks && rankingData.tasks.length > 0 ? (
              rankingData.tasks.map((item, idx) => (
                <tr key={item.task_id} className="hover:bg-slate-900/50 transition">
                  <td className="px-4 py-3 font-bold text-slate-400">#{idx + 1}</td>
                  <td className="px-4 py-3">
                    <div className="font-bold text-blue-400">{item.task_id}</div>
                    <div className="font-sans text-xs text-slate-200 truncate max-w-sm" title={item.title}>
                      {item.title}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-sans">
                    {item.department === "ENGINEERING" && (
                      <span className="text-amber-400 font-semibold">ENG</span>
                    )}
                    {item.department === "TRD" && (
                      <span className="text-sky-400 font-semibold">TRD</span>
                    )}
                    {item.department === "SNT" && (
                      <span className="text-emerald-400 font-semibold">SNT</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-300">{item.section_id}</td>
                  <td className="px-4 py-3">
                    <span className="text-sm font-bold text-white">
                      {item.score.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-sans">{getBandBadge(item.priority_band)}</td>
                  <td className="px-4 py-3">
                    <div className="space-y-1 font-sans text-[11px]">
                      {/* Stacked bar */}
                      <div className="flex h-2 w-full overflow-hidden rounded bg-slate-800">
                        <div
                          style={{ width: `${item.contributions.criticality}%` }}
                          title={`Criticality: ${item.contributions.criticality.toFixed(1)}`}
                          className="bg-purple-500"
                        />
                        <div
                          style={{ width: `${item.contributions.defect_severity}%` }}
                          title={`Defect Severity: ${item.contributions.defect_severity.toFixed(1)}`}
                          className="bg-amber-500"
                        />
                        <div
                          style={{ width: `${item.contributions.overdue_ratio}%` }}
                          title={`Overdue Ratio: ${item.contributions.overdue_ratio.toFixed(1)}`}
                          className="bg-rose-500"
                        />
                        <div
                          style={{ width: `${item.contributions.traffic_impact}%` }}
                          title={`Traffic Impact: ${item.contributions.traffic_impact.toFixed(1)}`}
                          className="bg-blue-500"
                        />
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>Crit: {item.contributions.criticality.toFixed(0)}</span>
                        <span>Sev: {item.contributions.defect_severity.toFixed(0)}</span>
                        <span>Due: {item.contributions.overdue_ratio.toFixed(0)}</span>
                        <span>Traf: {item.contributions.traffic_impact.toFixed(0)}</span>
                      </div>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No priority items found for current criteria.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
