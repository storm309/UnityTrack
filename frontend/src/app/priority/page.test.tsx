import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PriorityPage from "./page";
import { Providers } from "../providers";
import * as apiClient from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  getPriorityRanking: vi.fn(),
}));

describe("PriorityPage Component", () => {
  it("renders priority scoring sliders and tasks ranking", async () => {
    vi.mocked(apiClient.getPriorityRanking).mockResolvedValueOnce({
      total_tasks: 1,
      weights_used: {
        criticality: 0.35,
        defect_severity: 0.25,
        overdue_ratio: 0.25,
        traffic_impact: 0.15,
      },
      band_counts: { CRITICAL: 1 },
      tasks: [
        {
          task_id: "TASK-001",
          title: "Critical Rail Defect Repair",
          department: "ENGINEERING",
          section_id: "SEC-01",
          score: 88.5,
          rank: 1,
          priority_band: "CRITICAL",
          contributions: {
            criticality: 35.0,
            defect_severity: 25.0,
            overdue_ratio: 20.0,
            traffic_impact: 8.5,
          },
          factors_normalized: {
            criticality: 1.0,
            defect_severity: 1.0,
            overdue_ratio: 0.8,
            traffic_impact: 0.56,
          },
          raw_factors: {
            criticality: 5,
            defect_severity: 5,
            overdue_ratio: 1.2,
            traffic_impact: 0.8,
          },
        },
      ],
    });

    render(
      <Providers>
        <PriorityPage />
      </Providers>
    );

    expect(screen.getByText("Multi-Criteria Priority Scoring")).toBeInTheDocument();
    expect(screen.getByText("Section 2")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("TASK-001")).toBeInTheDocument();
      expect(screen.getByText("Critical Rail Defect Repair")).toBeInTheDocument();
      expect(screen.getByText("88.5")).toBeInTheDocument();
      expect(screen.getByText("CRITICAL (80-100)")).toBeInTheDocument();
    });
  });
});

