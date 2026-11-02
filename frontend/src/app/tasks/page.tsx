"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTasks, getSections, createTask, deleteTask, TaskCreate } from "@/lib/api-client";
import { PageHeader } from "@/components/PageHeader";
import {
  Wrench,
  Zap,
  Shield,
  Plus,
  Search,
  Filter,
  Trash2,
  Clock,
  Users,
  X,
} from "lucide-react";

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [departmentFilter, setDepartmentFilter] = useState<string>("");
  const [sectionFilter, setSectionFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState<Partial<TaskCreate>>({
    id: "TASK-099",
    title: "",
    department: "ENGINEERING",
    section_id: "SEC-01",
    asset_type: "Rails",
    duration_min: 120,
    earliest_start: 0,
    deadline: 1440,
    criticality: 3,
    defect_severity: 3,
    traffic_impact: 0.5,
    crew_needed: 2,
    requires_power_off: false,
    requires_track_block: true,
    due_date: "2026-11-15",
  });

  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks", departmentFilter, sectionFilter],
    queryFn: () =>
      getTasks({
        department: departmentFilter || undefined,
        sectionId: sectionFilter || undefined,
      }),
  });

  const { data: sections } = useQuery({
    queryKey: ["sections"],
    queryFn: () => getSections(),
  });

  const createMutation = useMutation({
    mutationFn: (payload: TaskCreate) => createTask(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setIsModalOpen(false);
      setFormError(null);
      setFormData({
        id: "TASK-099",
        title: "",
        department: "ENGINEERING",
        section_id: "SEC-01",
        asset_type: "Rails",
        duration_min: 120,
        earliest_start: 0,
        deadline: 1440,
        criticality: 3,
        defect_severity: 3,
        traffic_impact: 0.5,
        crew_needed: 2,
        requires_power_off: false,
        requires_track_block: true,
        due_date: "2026-11-15",
      });
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const filteredTasks = tasks?.filter((t) => {
    const matchesSearch =
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.asset_type.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title || !formData.id || !formData.section_id) {
      setFormError("Please fill all required fields");
      return;
    }
    createMutation.mutate(formData as TaskCreate);
  };

  const getDeptBadge = (dept: string) => {
    switch (dept) {
      case "ENGINEERING":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-400 border border-amber-500/20">
            <Wrench className="h-3 w-3" />
            Engineering
          </span>
        );
      case "TRD":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-sky-500/10 px-2 py-0.5 text-[11px] font-semibold text-sky-400 border border-sky-500/20">
            <Zap className="h-3 w-3" />
            Traction (TRD)
          </span>
        );
      case "SNT":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/20">
            <Shield className="h-3 w-3" />
            Signal & Telecom
          </span>
        );
      default:
        return <span className="text-slate-400">{dept}</span>;
    }
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-6">
      <PageHeader
        title="Unified Maintenance Tasks"
        badge="Section 1"
        description="Unified cross-departmental register of Engineering track works, TRD power maintenance, and S&T signaling jobs"
        actions={
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-500 transition"
          >
            <Plus className="h-4 w-4" />
            <span>Create Task</span>
          </button>
        }
      />

      {/* Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Filter className="h-3.5 w-3.5" />
            <span>Filter:</span>
          </div>

          {/* Department filter */}
          <div className="flex items-center space-x-1">
            {["", "ENGINEERING", "TRD", "SNT"].map((dept) => (
              <button
                key={dept}
                onClick={() => setDepartmentFilter(dept)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                  departmentFilter === dept
                    ? "bg-blue-600 text-white"
                    : "bg-slate-950/60 text-slate-400 hover:text-white border border-slate-800"
                }`}
              >
                {dept === "" ? "All Departments" : dept}
              </button>
            ))}
          </div>

          {/* Section filter */}
          <select
            value={sectionFilter}
            onChange={(e) => setSectionFilter(e.target.value)}
            className="rounded-lg border border-slate-800 bg-slate-950/70 px-2.5 py-1 text-xs text-slate-300 focus:outline-none"
          >
            <option value="">All Sections</option>
            {sections?.map((sec) => (
              <option key={sec.id} value={sec.id}>
                {sec.id} ({sec.name})
              </option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search task title, ID or asset..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full md:w-64 rounded-lg border border-slate-800 bg-slate-950/70 pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Tasks Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-800 bg-slate-950/70 text-slate-400">
            <tr>
              <th className="px-4 py-3 font-semibold">Task ID</th>
              <th className="px-4 py-3 font-semibold">Department</th>
              <th className="px-4 py-3 font-semibold">Task Description</th>
              <th className="px-4 py-3 font-semibold">Section</th>
              <th className="px-4 py-3 font-semibold">Duration</th>
              <th className="px-4 py-3 font-semibold">Criticality</th>
              <th className="px-4 py-3 font-semibold">Severity</th>
              <th className="px-4 py-3 font-semibold">Block Type</th>
              <th className="px-4 py-3 font-semibold">Crew</th>
              <th className="px-4 py-3 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {isLoading ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-slate-400">
                  Loading tasks...
                </td>
              </tr>
            ) : filteredTasks && filteredTasks.length > 0 ? (
              filteredTasks.map((t) => (
                <tr key={t.id} className="hover:bg-slate-900/50 transition">
                  <td className="px-4 py-3 font-mono font-bold text-blue-400">{t.id}</td>
                  <td className="px-4 py-3">{getDeptBadge(t.department)}</td>
                  <td className="px-4 py-3 font-medium text-slate-200 max-w-xs truncate" title={t.title}>
                    {t.title}
                    <div className="text-[10px] text-slate-500 font-mono">Asset: {t.asset_type}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-300">{t.section_id}</td>
                  <td className="px-4 py-3 font-mono text-slate-300">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3 text-slate-500" />
                      {t.duration_min}m
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block font-mono font-bold ${
                        t.criticality >= 4 ? "text-rose-400" : t.criticality === 3 ? "text-amber-400" : "text-slate-400"
                      }`}
                    >
                      {t.criticality}/5
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block font-mono font-bold ${
                        t.defect_severity >= 4 ? "text-rose-400" : "text-slate-400"
                      }`}
                    >
                      {t.defect_severity}/5
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      {t.requires_track_block && (
                        <span className="text-[10px] text-amber-400 font-mono">Line Block</span>
                      )}
                      {t.requires_power_off && (
                        <span className="text-[10px] text-sky-400 font-mono">Power Off</span>
                      )}
                      {!t.requires_track_block && !t.requires_power_off && (
                        <span className="text-[10px] text-slate-500 font-mono">Cess Work</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-300">
                    <span className="inline-flex items-center gap-1">
                      <Users className="h-3 w-3 text-slate-500" />
                      {t.crew_needed}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => deleteMutation.mutate(t.id)}
                      disabled={deleteMutation.isPending}
                      className="text-slate-500 hover:text-rose-400 transition"
                      title="Delete Task"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                  No tasks found matching filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create Task Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-semibold text-white">Create Maintenance Task</h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-3 text-xs text-rose-300">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Task ID</label>
                  <input
                    type="text"
                    required
                    value={formData.id || ""}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Department</label>
                  <select
                    value={formData.department}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        department: e.target.value as "ENGINEERING" | "TRD" | "SNT",
                      })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                  >
                    <option value="ENGINEERING">Engineering (Civil/Track)</option>
                    <option value="TRD">Traction (TRD/OHE)</option>
                    <option value="SNT">Signal & Telecom (S&T)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Task Title / Description</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. [ENG] Rail Weld Defect Ultrasonic Repair"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Section ID</label>
                  <select
                    value={formData.section_id}
                    onChange={(e) => setFormData({ ...formData, section_id: e.target.value })}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                  >
                    {sections?.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.id} ({s.name})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Asset Type</label>
                  <input
                    type="text"
                    value={formData.asset_type}
                    onChange={(e) => setFormData({ ...formData, asset_type: e.target.value })}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Duration (min)</label>
                  <input
                    type="number"
                    min={15}
                    max={480}
                    value={formData.duration_min}
                    onChange={(e) =>
                      setFormData({ ...formData, duration_min: Number(e.target.value) })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Criticality (1-5)</label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={formData.criticality}
                    onChange={(e) =>
                      setFormData({ ...formData, criticality: Number(e.target.value) })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Severity (1-5)</label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={formData.defect_severity}
                    onChange={(e) =>
                      setFormData({ ...formData, defect_severity: Number(e.target.value) })
                    }
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex items-center space-x-2 rounded-lg border border-slate-800 bg-slate-950 p-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.requires_track_block}
                    onChange={(e) =>
                      setFormData({ ...formData, requires_track_block: e.target.checked })
                    }
                    className="rounded border-slate-700 text-blue-600 focus:ring-0"
                  />
                  <span className="text-slate-300">Requires Track Line Block</span>
                </label>

                <label className="flex items-center space-x-2 rounded-lg border border-slate-800 bg-slate-950 p-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.requires_power_off}
                    onChange={(e) =>
                      setFormData({ ...formData, requires_power_off: e.target.checked })
                    }
                    className="rounded border-slate-700 text-blue-600 focus:ring-0"
                  />
                  <span className="text-slate-300">Requires TRD Power Off</span>
                </label>
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:bg-slate-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-1.5 font-semibold text-white hover:bg-blue-500 disabled:opacity-50 transition"
                >
                  {createMutation.isPending ? "Creating..." : "Save Task"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
