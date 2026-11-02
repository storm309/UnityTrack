"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCorridors, getCorridor, getSections, getTrains, getWindows } from "@/lib/api-client";
import { PageHeader } from "@/components/PageHeader";
import {
  Train,
  Search,
} from "lucide-react";

export default function CorridorsPage() {
  const [selectedCorridorId, setSelectedCorridorId] = useState<string>("CORR-01");
  const [activeTab, setActiveTab] = useState<"sections" | "trains" | "windows">("sections");
  const [searchFilter, setSearchFilter] = useState("");

  const { data: corridors } = useQuery({
    queryKey: ["corridors"],
    queryFn: getCorridors,
  });

  const { data: corridorDetail } = useQuery({
    queryKey: ["corridor", selectedCorridorId],
    queryFn: () => getCorridor(selectedCorridorId),
    enabled: Boolean(selectedCorridorId),
  });

  const { data: sections } = useQuery({
    queryKey: ["sections", selectedCorridorId],
    queryFn: () => getSections(selectedCorridorId),
  });

  const { data: trains } = useQuery({
    queryKey: ["trains", selectedCorridorId],
    queryFn: () => getTrains({ corridorId: selectedCorridorId }),
  });

  const { data: windows } = useQuery({
    queryKey: ["windows"],
    queryFn: () => getWindows(),
  });

  const totalLengthKm =
    sections?.reduce((sum, s) => sum + (s.km_end - s.km_start), 0) || 0;

  const filteredSections = sections?.filter(
    (s) =>
      s.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      s.id.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const filteredTrains = trains?.filter(
    (t) =>
      t.train_no.toLowerCase().includes(searchFilter.toLowerCase()) ||
      t.section_id.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-6">
      <PageHeader
        title="Corridors & Network Assets"
        badge="Section 1"
        description="Physical track topology, kilometer posts, timetable train paths, and maintenance block windows"
      />

      {/* Corridor Selector bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Active Corridor:
        </span>
        <div className="flex flex-wrap gap-2">
          {corridors?.map((corr) => (
            <button
              key={corr.id}
              onClick={() => setSelectedCorridorId(corr.id)}
              className={`inline-flex items-center space-x-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                selectedCorridorId === corr.id
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-950/70 text-slate-300 hover:bg-slate-800 border border-slate-800"
              }`}
            >
              <Train className="h-3.5 w-3.5" />
              <span>{corr.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Corridor Quick Stats */}
      {corridorDetail && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <span className="text-xs text-slate-400">Total Route Length</span>
            <div className="mt-1 text-2xl font-bold text-white font-mono">
              {totalLengthKm.toFixed(1)} km
            </div>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <span className="text-xs text-slate-400">Track Sections</span>
            <div className="mt-1 text-2xl font-bold text-blue-400 font-mono">
              {corridorDetail.sections.length} blocks
            </div>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <span className="text-xs text-slate-400">Timetable Trains</span>
            <div className="mt-1 text-2xl font-bold text-amber-400 font-mono">
              {trains?.length ?? 0} slots
            </div>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <span className="text-xs text-slate-400">Maintenance Windows</span>
            <div className="mt-1 text-2xl font-bold text-emerald-400 font-mono">
              {windows?.length ?? 0} windows
            </div>
          </div>
        </div>
      )}

      {/* Tab Controls & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setActiveTab("sections")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "sections"
                ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Track Sections ({sections?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab("trains")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "trains"
                ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Timetable Train Slots ({trains?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab("windows")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "windows"
                ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Block Windows ({windows?.length ?? 0})
          </button>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search assets or train no..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-full sm:w-64 rounded-lg border border-slate-800 bg-slate-900/80 pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Sections Table View */}
      {activeTab === "sections" && (
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950/70 text-slate-400">
              <tr>
                <th className="px-4 py-3 font-semibold">Section ID</th>
                <th className="px-4 py-3 font-semibold">Section Name</th>
                <th className="px-4 py-3 font-semibold">Corridor</th>
                <th className="px-4 py-3 font-semibold">KM Range</th>
                <th className="px-4 py-3 font-semibold">Length (km)</th>
                <th className="px-4 py-3 font-semibold">Sequence Index</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredSections?.map((sec) => {
                const len = sec.km_end - sec.km_start;
                return (
                  <tr key={sec.id} className="hover:bg-slate-900/50 transition">
                    <td className="px-4 py-3 font-bold text-blue-400">{sec.id}</td>
                    <td className="px-4 py-3 font-sans font-medium text-slate-200">{sec.name}</td>
                    <td className="px-4 py-3 text-slate-400">{sec.corridor_id}</td>
                    <td className="px-4 py-3 text-slate-300">
                      KM {sec.km_start.toFixed(1)} → KM {sec.km_end.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-slate-200 font-bold">{len.toFixed(1)} km</td>
                    <td className="px-4 py-3 text-slate-400">#{sec.order_index}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Train Slots Table View */}
      {activeTab === "trains" && (
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950/70 text-slate-400">
              <tr>
                <th className="px-4 py-3 font-semibold">Slot ID</th>
                <th className="px-4 py-3 font-semibold">Train Number</th>
                <th className="px-4 py-3 font-semibold">Section</th>
                <th className="px-4 py-3 font-semibold">Corridor</th>
                <th className="px-4 py-3 font-semibold">Start Minute</th>
                <th className="px-4 py-3 font-semibold">End Minute</th>
                <th className="px-4 py-3 font-semibold">Duration</th>
                <th className="px-4 py-3 font-semibold">Priority</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredTrains?.map((train) => (
                <tr key={train.id} className="hover:bg-slate-900/50 transition">
                  <td className="px-4 py-3 font-bold text-blue-400">{train.id}</td>
                  <td className="px-4 py-3 font-bold text-amber-400">{train.train_no}</td>
                  <td className="px-4 py-3 text-slate-300">{train.section_id}</td>
                  <td className="px-4 py-3 text-slate-400">{train.corridor_id}</td>
                  <td className="px-4 py-3 text-slate-300">
                    Day {Math.floor(train.start_min / 1440) + 1} ({train.start_min % 1440}m)
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    Day {Math.floor(train.end_min / 1440) + 1} ({train.end_min % 1440}m)
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {train.end_min - train.start_min} min
                  </td>
                  <td className="px-4 py-3 text-emerald-400 font-bold">P{train.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Maintenance Windows View */}
      {activeTab === "windows" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {windows?.map((win) => (
            <div
              key={win.id}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-blue-400">{win.id}</span>
                {win.is_night_window && (
                  <span className="rounded bg-indigo-500/15 px-2 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/30">
                    Night Window
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-300">
                <span className="text-slate-500">Section: </span>
                <span className="font-mono font-medium">{win.section_id}</span>
              </div>
              <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-2 border-t border-slate-800">
                <span>Start: {win.start_min}m</span>
                <span>End: {win.end_min}m</span>
                <span className="text-emerald-400 font-bold">{win.duration_min} min</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
