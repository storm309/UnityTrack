import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import BundlesPage from "./page";
import { Providers } from "../providers";
import * as apiClient from "@/lib/api-client";
import type { CandidateBundlesListResponse } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  getCandidateBundles: vi.fn(),
  checkTasksCompatibility: vi.fn(),
  getTasks: vi.fn(),
  getSections: vi.fn(),
}));

describe("BundlesPage Component", () => {
  it("renders bundles candidate cards and pairwise validator", async () => {
    vi.mocked(apiClient.getCandidateBundles).mockResolvedValueOnce({
      total_candidates: 1,
      cross_departmental_count: 1,
      total_potential_savings_min: 60,
      candidates: [
        {
          bundle_id: "BND-001",
          task_ids: ["TASK-001", "TASK-002"],
          section_id: "SEC-01",
          corridor_id: "CORR-01",
          departments: ["TRD", "SNT"],
          is_cross_departmental: true,
          execution_mode: "PARALLEL",
          duration_min: 120,
          disruption_savings_min: 60,
          efficiency_gain_pct: 33.3,
          tasks_summary: [
            {
              id: "TASK-001",
              title: "[TRD] OHE Maintenance",
              department: "TRD",
              asset_type: "Catenary",
              duration_min: 120,
              priority_score: 75.0,
            },
            {
              id: "TASK-002",
              title: "[SNT] Signal Relays",
              department: "SNT",
              asset_type: "Signals",
              duration_min: 60,
              priority_score: 70.0,
            },
          ],
        },
      ],
    } as unknown as CandidateBundlesListResponse);
    vi.mocked(apiClient.getTasks).mockResolvedValueOnce([]);
    vi.mocked(apiClient.getSections).mockResolvedValueOnce([]);

    render(
      <Providers>
        <BundlesPage />
      </Providers>
    );

    expect(screen.getByText("Cross-Departmental Task Bundling")).toBeInTheDocument();
    expect(screen.getByText("Pairwise Compatibility Validator")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("BND-001")).toBeInTheDocument();
      expect(screen.getByText("+60m saved (33%)")).toBeInTheDocument();
    });
  });
});
