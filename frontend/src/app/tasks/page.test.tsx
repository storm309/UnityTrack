import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import TasksPage from "./page";
import { Providers } from "../providers";
import * as apiClient from "@/lib/api-client";
import type { TaskResponse } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  getTasks: vi.fn(),
  getSections: vi.fn(),
  createTask: vi.fn(),
  deleteTask: vi.fn(),
}));

describe("TasksPage Component", () => {
  it("renders tasks table and department indicators", async () => {
    vi.mocked(apiClient.getTasks).mockResolvedValueOnce([
      {
        id: "TASK-001",
        title: "[ENG] Track Tamping & Lining",
        department: "ENGINEERING",
        section_id: "SEC-01",
        asset_type: "Ballast",
        duration_min: 180,
        earliest_start: 0,
        deadline: 1440,
        criticality: 4,
        defect_severity: 3,
        traffic_impact: 0.5,
        crew_needed: 3,
        requires_power_off: false,
        requires_track_block: true,
        status: "PENDING",
      },
    ] as unknown as TaskResponse[]);
    vi.mocked(apiClient.getSections).mockResolvedValueOnce([
      { id: "SEC-01", corridor_id: "CORR-01", name: "Section 1", km_start: 0, km_end: 20, order_index: 1 },
    ]);

    render(
      <Providers>
        <TasksPage />
      </Providers>
    );

    expect(screen.getByText("Unified Maintenance Tasks")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("TASK-001")).toBeInTheDocument();
      expect(screen.getByText("[ENG] Track Tamping & Lining")).toBeInTheDocument();
      expect(screen.getByText("Engineering")).toBeInTheDocument();
      expect(screen.getByText("Line Block")).toBeInTheDocument();
    });
  });
});
