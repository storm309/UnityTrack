"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getScenarios,
  runScenario,
  compareScenarios,
  deleteScenario,
  getSections,
  ScenarioRunRequest,
  ScenarioCompareRequest,
  ScenarioComparisonResponse,
  ScenarioSummaryResponse,
} from "@/lib/api-client";
import { PageHeader } from "@/components/PageHeader";
import {
  GitBranch,
  Play,
  Trash2,
  Users,
  CloudRain,
  AlertTriangle,
  Scale,
  Award,
} from "lucide-react";

export default function ScenariosPage() {
  const queryClient = useQueryClient();
  const [isRunModalOpen, setIsRunModalOpen] = useState(false);
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<ScenarioComparisonResponse | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Form State
  const [scenarioName, setScenarioName] = useState("Engineering Crew Crunch (Capacity=2)");
  const [scenarioDesc, setScenarioDesc] = useState("Simulate shortage of civil track maintenance gangs");
  const [engCap, setEngCap] = useState(2);
  const [trdCap, setTrdCap] = useState(2);
  const [sntCap, setSntCap] = useState(2);

  const [hasRestriction, setHasRestriction] = useState(false);
  const [restrictedSection, setRestrictedSection] = useState("SEC-02");
  const [restrictStart, setRestrictStart] = useState(360);
  const [restrictEnd, setRestrictEnd] = useState(1080);

  const [hasEmergency, setHasEmergency] = useState(false);
  const [emergencyTitle, setEmergencyTitle] = useState("Emergency Rail Defect Ultrasonic Replacement");
  const [emergencyDept, setEmergencyDept] = useState("ENGINEERING");
  const [emergencySection, setEmergencySection] = useState("SEC-03");

  const { data: scenarios, isLoading: scenariosLoading } = useQuery({
    queryKey: ["scenarios"],
    queryFn: getScenarios,
  });

  const { data: sections } = useQuery({
    queryKey: ["sections"],
    queryFn: () => getSections(),
  });

  const runMutation = useMutation({
    mutationFn: (payload: ScenarioRunRequest) => runScenario(payload),
    onSuccess: (newScen) => {
      queryClient.invalidateQueries({ queryKey: ["scenarios"] });
      setIsRunModalOpen(false);
      setSelectedScenarioIds((prev) => [...prev, newScen.id]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteScenario(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scenarios"] });
      setComparisonResult(null);
    },
  });

  const compareMutation = useMutation({
    mutationFn: (payload: ScenarioCompareRequest) => compareScenarios(payload),
    onSuccess: (data) => {
      setComparisonResult(data);
      setCompareError(null);
    },
    onError: (err: Error) => {
      setCompareError(err.message);
    },
  });

  const handleToggleSelectScenario = (id: string) => {
    setSelectedScenarioIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleRunSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: ScenarioRunRequest = {
      name: scenarioName,
      description: scenarioDesc,
      params: {
        capacity_overrides: {
          ENGINEERING: engCap,
          TRD: trdCap,
          SNT: sntCap,
        },
        restrict_sections: hasRestriction
          ? [
              {
                section_id: restrictedSection,
                start_min: restrictStart,
                end_min: restrictEnd,
                restriction_type: "WEATHER_OR_CLOSURE",
                reason: "Emergency Track Weather/Bridge Closure",
              },
            ]
          : undefined,
        add_tasks: hasEmergency
          ? [
              {
                title: emergencyTitle,
                department: emergencyDept,
                section_id: emergencySection,
                asset_type: "Rails",
                duration_min: 120,
                earliest_start: 0,
                deadline: 2880,
                criticality: 5,
                defect_severity: 5,
                traffic_impact: 0.9,
                crew_needed: 3,
                requires_track_block: true,
                requires_power_off: emergencyDept === "TRD",
              },
            ]
          : undefined,
      },
      time_limit_seconds: 30,
      save_scenario: true,
    };
    runMutation.mutate(payload);
  };

  const handleCompareClick = () => {
    if (selectedScenarioIds.length < 1) {
      setCompareError("Please select at least 1 scenario to compare against the baseline");
      return;
    }
    const compareReq: ScenarioCompareRequest = {
      scenarios: selectedScenarioIds.map((id) => {
        const match = scenarios?.find((s: ScenarioSummaryResponse) => s.id === id);
        return {
          name: match?.name || id,
          scenario_id: id,
        };
      }),
      include_baseline: true,
      time_limit_seconds: 20,
    };
    compareMutation.mutate(compareReq);
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-6">
      <PageHeader
        title="What-If Scenario Simulator"
        badge="Section 5"
        description="Simulate real-world operational disruptions: labor bottlenecks, timetable train traffic surges, speed restrictions, and weather storm windows"
        actions={
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsRunModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-cyan-500 transition"
            >
              <Play className="h-3.5 w-3.5 fill-current" />
              <span>Simulate New Scenario</span>
            </button>
            <button
              onClick={handleCompareClick}
              disabled={selectedScenarioIds.length === 0 || compareMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-purple-500 disabled:opacity-50 transition"
            >
              <Scale className="h-3.5 w-3.5" />
              <span>Compare Selected ({selectedScenarioIds.length})</span>
            </button>
          </div>
        }
      />

      {/* Preset Simulation Shortcuts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <button
          onClick={() => {
            setScenarioName("Severe Crew Bottleneck (ENG=1, TRD=1)");
            setScenarioDesc("Simulate severe labor strike or peak festival leave");
            setEngCap(1);
            setTrdCap(1);
            setSntCap(2);
            setHasRestriction(false);
            setHasEmergency(false);
            setIsRunModalOpen(true);
          }}
          className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-left hover:border-cyan-500/50 hover:bg-slate-900/70 transition"
        >
          <div className="flex items-center gap-2 text-cyan-400 font-semibold text-xs">
            <Users className="h-4 w-4" />
            <span>Severe Crew Bottleneck</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 leading-tight">
            Force maximum 1 gang each for Track & TRD works
          </p>
        </button>

        <button
          onClick={() => {
            setScenarioName("Monsoon Bridge Line Closure (SEC-02)");
            setScenarioDesc("Waterlogging restricts track section for 12 hours");
            setEngCap(2);
            setTrdCap(2);
            setSntCap(2);
            setHasRestriction(true);
            setRestrictedSection("SEC-02");
            setRestrictStart(360);
            setRestrictEnd(1080);
            setHasEmergency(false);
            setIsRunModalOpen(true);
          }}
          className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-left hover:border-blue-500/50 hover:bg-slate-900/70 transition"
        >
          <div className="flex items-center gap-2 text-blue-400 font-semibold text-xs">
            <CloudRain className="h-4 w-4" />
            <span>Section Closure (SEC-02)</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 leading-tight">
            12-hour block closure due to weather flood alerts
          </p>
        </button>

        <button
          onClick={() => {
            setScenarioName("Urgent Rail Fracture Defect Injection");
            setScenarioDesc("Critical flaw detected by ultrasonic testing car");
            setEngCap(2);
            setTrdCap(2);
            setSntCap(2);
            setHasRestriction(false);
            setHasEmergency(true);
            setEmergencyTitle("Emergency Rail Fracture Replacement");
            setEmergencyDept("ENGINEERING");
            setEmergencySection("SEC-01");
            setIsRunModalOpen(true);
          }}
          className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-left hover:border-rose-500/50 hover:bg-slate-900/70 transition"
        >
          <div className="flex items-center gap-2 text-rose-400 font-semibold text-xs">
            <AlertTriangle className="h-4 w-4" />
            <span>Emergency Defect Injection</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 leading-tight">
            Inject emergency task with Criticality 5 into active timetable
          </p>
        </button>
      </div>

      {/* Multi-Scenario Side-by-Side Comparison Matrix */}
      {comparisonResult && (
        <div className="rounded-xl border border-purple-500/30 bg-purple-950/20 p-5 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-purple-500/20 pb-3">
            <div className="flex items-center space-x-2">
              <Scale className="h-4 w-4 text-purple-400" />
              <h2 className="text-sm font-semibold text-white">
                Multi-Scenario Comparative Decision Matrix ({comparisonResult.scenarios_evaluated} Evaluated)
              </h2>
            </div>
            {comparisonResult.best_scenario_name && (
              <div className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
                <Award className="h-4 w-4" />
                <span>Recommended: {comparisonResult.best_scenario_name}</span>
              </div>
            )}
          </div>

          {comparisonResult.best_scenario_reason && (
            <p className="text-xs text-purple-200/90 leading-relaxed bg-purple-900/30 p-3 rounded-lg border border-purple-500/20">
              <span className="font-semibold text-white">Decision Justification: </span>
              {comparisonResult.best_scenario_reason}
            </p>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-purple-500/20 bg-purple-950/50 text-slate-300">
                <tr>
                  <th className="px-4 py-3 font-semibold font-sans">Scenario Candidate</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Total Blocks</th>
                  <th className="px-4 py-3 font-semibold">Disruption (min)</th>
                  <th className="px-4 py-3 font-semibold">Cross-Dept Blocks</th>
                  <th className="px-4 py-3 font-semibold">Delayed Tasks</th>
                  <th className="px-4 py-3 font-semibold">Delay Min</th>
                  <th className="px-4 py-3 font-semibold">Solve Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-purple-500/10">
                {comparisonResult.comparison_table.map((row) => {
                  const isBest = row.name === comparisonResult.best_scenario_name;
                  return (
                    <tr
                      key={row.name}
                      className={isBest ? "bg-emerald-950/30 font-bold" : "hover:bg-purple-900/20"}
                    >
                      <td className="px-4 py-3 font-sans text-slate-100 flex items-center gap-2">
                        {isBest && <Award className="h-3.5 w-3.5 text-emerald-400 shrink-0" />}
                        <span>{row.name}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] ${
                            row.status === "OPTIMAL"
                              ? "bg-emerald-500/15 text-emerald-400"
                              : "bg-amber-500/15 text-amber-400"
                          }`}
                        >
                          {row.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-white">{row.total_blocks}</td>
                      <td className="px-4 py-3 text-cyan-300">{row.total_disruption_minutes}m</td>
                      <td className="px-4 py-3 text-indigo-300">{row.cross_departmental_blocks}</td>
                      <td className="px-4 py-3">
                        <span className={row.delayed_tasks > 0 ? "text-rose-400" : "text-emerald-400"}>
                          {row.delayed_tasks}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-300">{row.total_delay_minutes}m</td>
                      <td className="px-4 py-3 text-slate-400">{row.solve_time_seconds.toFixed(2)}s</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {compareError && (
        <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-3 text-xs text-rose-300">
          {compareError}
        </div>
      )}

      {/* Scenario Catalog List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Simulated Scenario Catalog</h2>
          <span className="text-xs text-slate-400 font-mono">
            {scenarios?.length ?? 0} scenarios saved
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950/70 text-slate-400">
              <tr>
                <th className="px-4 py-3 font-semibold">Select</th>
                <th className="px-4 py-3 font-semibold">Scenario ID & Name</th>
                <th className="px-4 py-3 font-semibold">Blocks</th>
                <th className="px-4 py-3 font-semibold">Disruption</th>
                <th className="px-4 py-3 font-semibold">Delayed Tasks</th>
                <th className="px-4 py-3 font-semibold">Penalty Score</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {scenariosLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                    Loading scenario catalog...
                  </td>
                </tr>
              ) : scenarios && scenarios.length > 0 ? (
                scenarios.map((s: ScenarioSummaryResponse) => {
                  const isChecked = selectedScenarioIds.includes(s.id);
                  return (
                    <tr key={s.id} className="hover:bg-slate-900/50 transition">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleSelectScenario(s.id)}
                          className="rounded border-slate-700 text-purple-600 focus:ring-0 cursor-pointer"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-bold text-cyan-400">{s.id}</div>
                        <div className="font-sans text-xs text-slate-200">{s.name}</div>
                      </td>
                      <td className="px-4 py-3 text-white font-bold">{s.total_blocks}</td>
                      <td className="px-4 py-3 text-white font-bold">{s.total_disruption_minutes}m</td>
                      <td className="px-4 py-3">
                        <span className={s.delayed_tasks > 0 ? "text-rose-400" : "text-emerald-400"}>
                          {s.delayed_tasks}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-amber-400 font-bold">{s.composite_penalty_score.toFixed(0)}</td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-400">
                          {s.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => deleteMutation.mutate(s.id)}
                          className="text-slate-500 hover:text-rose-400 transition"
                          title="Delete Scenario"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    No scenarios simulated yet. Click &quot;Simulate New Scenario&quot; above to run one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Simulate Modal */}
      {isRunModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <GitBranch className="h-4 w-4 text-cyan-400" />
                <h2 className="text-sm font-semibold text-white">Simulate What-If Scenario</h2>
              </div>
              <button
                onClick={() => setIsRunModalOpen(false)}
                className="text-slate-400 hover:text-white text-xs"
              >
                Close
              </button>
            </div>

            <form onSubmit={handleRunSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Scenario Name</label>
                <input
                  type="text"
                  required
                  value={scenarioName}
                  onChange={(e) => setScenarioName(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Description / Notes</label>
                <input
                  type="text"
                  value={scenarioDesc}
                  onChange={(e) => setScenarioDesc(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                />
              </div>

              {/* Crew capacity constraints */}
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <span className="font-semibold text-slate-300">Department Crew Gang Capacities</span>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-slate-400 mb-1">ENG Gangs</label>
                    <input
                      type="number"
                      min={1}
                      max={6}
                      value={engCap}
                      onChange={(e) => setEngCap(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">TRD Gangs</label>
                    <input
                      type="number"
                      min={1}
                      max={6}
                      value={trdCap}
                      onChange={(e) => setTrdCap(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">SNT Gangs</label>
                    <input
                      type="number"
                      min={1}
                      max={6}
                      value={sntCap}
                      onChange={(e) => setSntCap(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Section restriction overlay */}
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <label className="flex items-center space-x-2 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hasRestriction}
                    onChange={(e) => setHasRestriction(e.target.checked)}
                    className="rounded border-slate-700 text-cyan-600 focus:ring-0"
                  />
                  <span>Inject Section Restriction / Line Closure</span>
                </label>

                {hasRestriction && (
                  <div className="grid grid-cols-3 gap-3 pl-6 pt-1">
                    <div>
                      <label className="block text-slate-400 mb-1">Section</label>
                      <select
                        value={restrictedSection}
                        onChange={(e) => setRestrictedSection(e.target.value)}
                        className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                      >
                        {sections?.map((sec) => (
                          <option key={sec.id} value={sec.id}>
                            {sec.id}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Start (min)</label>
                      <input
                        type="number"
                        value={restrictStart}
                        onChange={(e) => setRestrictStart(Number(e.target.value))}
                        className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">End (min)</label>
                      <input
                        type="number"
                        value={restrictEnd}
                        onChange={(e) => setRestrictEnd(Number(e.target.value))}
                        className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Emergency task injection */}
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <label className="flex items-center space-x-2 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hasEmergency}
                    onChange={(e) => setHasEmergency(e.target.checked)}
                    className="rounded border-slate-700 text-rose-600 focus:ring-0"
                  />
                  <span>Inject Emergency Urgent Task</span>
                </label>

                {hasEmergency && (
                  <div className="space-y-2 pl-6 pt-1">
                    <div>
                      <label className="block text-slate-400 mb-1">Emergency Title</label>
                      <input
                        type="text"
                        value={emergencyTitle}
                        onChange={(e) => setEmergencyTitle(e.target.value)}
                        className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-slate-400 mb-1">Department</label>
                        <select
                          value={emergencyDept}
                          onChange={(e) => setEmergencyDept(e.target.value)}
                          className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                        >
                          <option value="ENGINEERING">Engineering</option>
                          <option value="TRD">TRD</option>
                          <option value="SNT">S&T</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">Section</label>
                        <select
                          value={emergencySection}
                          onChange={(e) => setEmergencySection(e.target.value)}
                          className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                        >
                          {sections?.map((sec) => (
                            <option key={sec.id} value={sec.id}>
                              {sec.id}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="pt-2 flex justify-end space-x-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsRunModalOpen(false)}
                  className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:bg-slate-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={runMutation.isPending}
                  className="rounded-lg bg-cyan-600 px-4 py-1.5 font-semibold text-white hover:bg-cyan-500 disabled:opacity-50 transition"
                >
                  {runMutation.isPending ? "Simulating CP-SAT..." : "Run Simulation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
