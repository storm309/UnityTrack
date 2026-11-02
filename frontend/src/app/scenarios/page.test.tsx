import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ScenariosPage from "./page";
import { Providers } from "../providers";
import * as apiClient from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  getScenarios: vi.fn(),
  runScenario: vi.fn(),
  compareScenarios: vi.fn(),
  deleteScenario: vi.fn(),
  getSections: vi.fn(),
}));

describe("ScenariosPage Component", () => {
  it("renders what-if scenario presets and scenario table", async () => {
    vi.mocked(apiClient.getScenarios).mockResolvedValueOnce([
      {
        id: "SCEN-001",
        name: "Severe Crew Shortage",
        created_at: "2026-11-02T12:00:00",
        status: "OPTIMAL",
        total_blocks: 44,
        total_disruption_minutes: 6800,
        delayed_tasks: 2,
        high_priority_delays: 0,
        composite_penalty_score: 8500,
      },
    ]);

    vi.mocked(apiClient.getSections).mockResolvedValueOnce([
      { id: "SEC-01", corridor_id: "CORR-01", name: "Section 1", km_start: 0, km_end: 25, order_index: 1 },
    ]);

    render(
      <Providers>
        <ScenariosPage />
      </Providers>
    );

    expect(screen.getByText("What-If Scenario Simulator")).toBeInTheDocument();
    expect(screen.getByText("Section 5")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Severe Crew Bottleneck")).toBeInTheDocument();
      expect(screen.getByText("SCEN-001")).toBeInTheDocument();
      expect(screen.getByText("Severe Crew Shortage")).toBeInTheDocument();
      expect(screen.getByText("6800m")).toBeInTheDocument();
    });
  });
});

