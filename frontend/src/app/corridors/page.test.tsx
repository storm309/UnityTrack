import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import CorridorsPage from "./page";
import { Providers } from "../providers";
import * as apiClient from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  getCorridors: vi.fn(),
  getCorridor: vi.fn(),
  getSections: vi.fn(),
  getTrains: vi.fn(),
  getWindows: vi.fn(),
}));

describe("CorridorsPage Component", () => {
  it("renders corridor title and assets correctly", async () => {
    vi.mocked(apiClient.getCorridors).mockResolvedValueOnce([
      { id: "CORR-01", name: "Northern Corridor" },
    ]);
    vi.mocked(apiClient.getCorridor).mockResolvedValueOnce({
      id: "CORR-01",
      name: "Northern Corridor",
      sections: [
        { id: "SEC-01", corridor_id: "CORR-01", name: "New Delhi - Ghaziabad", km_start: 0, km_end: 25, order_index: 1 },
      ],
    });
    vi.mocked(apiClient.getSections).mockResolvedValueOnce([
      { id: "SEC-01", corridor_id: "CORR-01", name: "New Delhi - Ghaziabad", km_start: 0, km_end: 25, order_index: 1 },
    ]);
    vi.mocked(apiClient.getTrains).mockResolvedValueOnce([
      { id: "TR-01", corridor_id: "CORR-01", section_id: "SEC-01", train_no: "12004", start_min: 360, end_min: 420, priority: 1 },
    ]);
    vi.mocked(apiClient.getWindows).mockResolvedValueOnce([
      { id: "WIN-01", section_id: "SEC-01", start_min: 120, end_min: 300, duration_min: 180, is_night_window: true },
    ]);

    render(
      <Providers>
        <CorridorsPage />
      </Providers>
    );

    expect(screen.getByText("Corridors & Network Assets")).toBeInTheDocument();
    expect(screen.getByText("Section 1")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Northern Corridor")).toBeInTheDocument();
      expect(screen.getByText("SEC-01")).toBeInTheDocument();
      expect(screen.getByText("New Delhi - Ghaziabad")).toBeInTheDocument();
    });
  });
});

