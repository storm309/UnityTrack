import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PlansPage from "./page";
import { Providers } from "../providers";
import * as apiClient from "@/lib/api-client";
import type { PlanResponse } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  getPlans: vi.fn(),
  getPlan: vi.fn(),
  generatePlan: vi.fn(),
  getCorridors: vi.fn(),
}));

describe("PlansPage Component", () => {
  it("renders optimizer plan schedule and baseline comparison", async () => {
    vi.mocked(apiClient.getPlans).mockResolvedValueOnce({
      total_plans: 1,
      plans: [
        {
          id: "PLAN-001",
          name: "Master 7-Day Plan",
          status: "OPTIMAL",
          created_at: "2026-11-02T10:00:00",
          total_blocks: 42,
          total_disruption_minutes: 6495,
          tasks_scheduled: 50,
          is_valid: true,
        },
      ],
    });

    vi.mocked(apiClient.getPlan).mockResolvedValueOnce({
      id: "PLAN-001",
      name: "Master 7-Day Plan",
      status: "OPTIMAL",
      created_at: "2026-11-02T10:00:00",
      metrics: {
        total_blocks: 42,
        total_disruption_minutes: 6495,
        tasks_scheduled: 50,
        delayed_tasks_count: 0,
        solve_time_seconds: 2.5,
        objective_value: 12000,
      },
      comparison: {
        baseline_blocks: 50,
        optimized_blocks: 42,
        block_reduction_count: 8,
        block_reduction_pct: 16.0,
        baseline_disruption_min: 8200,
        optimized_disruption_min: 6495,
        disruption_savings_min: 1705,
        disruption_savings_pct: 20.8,
      },
      validation: {
        is_valid: true,
        total_violations: 0,
        violations: [],
      },
      planned_blocks: [
        {
          id: "BLK-01",
          section_id: "SEC-01",
          start_min: 120,
          end_min: 300,
          duration_min: 180,
          requires_track_block: true,
          requires_power_off: true,
          tasks: [
            {
              task_id: "TASK-001",
              title: "Track Tamping",
              department: "ENGINEERING",
              section_id: "SEC-01",
            },
          ],
        },
      ],
    } as unknown as PlanResponse);

    vi.mocked(apiClient.getCorridors).mockResolvedValueOnce([
      { id: "CORR-01", name: "Northern Corridor" },
    ]);

    render(
      <Providers>
        <PlansPage />
      </Providers>
    );

    expect(screen.getByText("Constraint Optimizer Schedules")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("PLAN-001")).toBeInTheDocument();
      expect(screen.getByText("8 blocks")).toBeInTheDocument();
      expect(screen.getByText("1705 min")).toBeInTheDocument();
    });
  });
});
