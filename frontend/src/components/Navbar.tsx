"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getHealth, triggerSeed } from "@/lib/api-client";
import {
  Train,
  Activity,
  Layers,
  Wrench,
  Sliders,
  Calendar,
  GitBranch,
  RefreshCw,
  Database,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/corridors", label: "Corridors", icon: Train },
  { href: "/tasks", label: "Tasks", icon: Wrench },
  { href: "/priority", label: "Priority", icon: Sliders },
  { href: "/bundles", label: "Bundling", icon: Layers },
  { href: "/plans", label: "Optimizer Plans", icon: Calendar },
  { href: "/scenarios", label: "What-If Scenarios", icon: GitBranch },
];

export function Navbar() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [seedNotice, setSeedNotice] = useState<string | null>(null);

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15000,
  });

  const seedMutation = useMutation({
    mutationFn: () => triggerSeed(42, true),
    onSuccess: (data) => {
      queryClient.invalidateQueries();
      const count = Object.values(data.records || {}).reduce((a, b) => a + b, 0);
      setSeedNotice(`Database re-seeded! (${count} records initialized)`);
      setTimeout(() => setSeedNotice(null), 4000);
    },
    onError: (err: Error) => {
      setSeedNotice(`Seed failed: ${err.message}`);
      setTimeout(() => setSeedNotice(null), 4000);
    },
  });

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        {/* Brand */}
        <div className="flex items-center space-x-6">
          <Link href="/" className="flex items-center space-x-3 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 group-hover:bg-blue-600/30 transition">
              <Train className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">UnityTrack</span>
                <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-blue-400 border border-blue-500/20">
                  IR-Decision
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">Indian Railways Maintenance Intelligence</p>
            </div>
          </Link>

          {/* Navigation links */}
          <nav className="hidden lg:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`inline-flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${isActive
                    ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
                    : "text-slate-300 hover:bg-slate-900 hover:text-white"
                    }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Action Controls & Health Status */}
        <div className="flex items-center space-x-3">
          {seedNotice && (
            <span className="text-xs text-emerald-400 font-mono hidden md:inline animate-pulse">
              {seedNotice}
            </span>
          )}

          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            title="Seed Synthetic Database (50 tasks across 3 departments)"
            className="inline-flex items-center space-x-1.5 rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50 transition"
          >
            <Database className={`h-3.5 w-3.5 text-amber-400 ${seedMutation.isPending ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">
              {seedMutation.isPending ? "Seeding..." : "Seed DB"}
            </span>
          </button>

          {/* Live Status indicator */}
          <div className="flex items-center space-x-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1.5 text-xs">
            {healthLoading ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-slate-400" />
            ) : health?.status === "ok" ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <span className="font-mono text-emerald-400 text-[11px] hidden sm:inline">API Online</span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
                <span className="font-mono text-rose-400 text-[11px] hidden sm:inline">API Offline</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Mobile nav bar */}
      <div className="flex lg:hidden overflow-x-auto border-t border-slate-800/80 px-2 py-1.5 space-x-1 scrollbar-none">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`inline-flex shrink-0 items-center space-x-1 rounded-md px-2.5 py-1 text-[11px] font-medium transition ${isActive
                ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                : "text-slate-400 hover:bg-slate-900 hover:text-white"
                }`}
            >
              <Icon className="h-3 w-3" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </header>
  );
}
