import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import HomePage from "./page";
import { Providers } from "./providers";
import * as apiClient from "@/lib/api-client";

// Mock the API client function
vi.mock("@/lib/api-client", () => ({
  getHealth: vi.fn(),
}));

describe("HomePage Component", () => {
  it("renders loading state initially and then shows health status", async () => {
    vi.mocked(apiClient.getHealth).mockResolvedValueOnce({
      status: "ok",
      environment: "test",
      version: "0.1.0",
      database: "healthy",
    });

    render(
      <Providers>
        <HomePage />
      </Providers>
    );

    // Check title
    expect(screen.getByText("UnityTrack")).toBeInTheDocument();
    expect(screen.getByText("Section 0")).toBeInTheDocument();

    // Check departments are rendered
    expect(screen.getByText("Engineering (ENG)")).toBeInTheDocument();
    expect(screen.getByText("Traction (TRD)")).toBeInTheDocument();
    expect(screen.getByText("Signal & Telecom (SNT)")).toBeInTheDocument();

    // Wait for health data to display
    await waitFor(() => {
      expect(screen.getByText("healthy")).toBeInTheDocument();
      expect(screen.getByText("test")).toBeInTheDocument();
      expect(screen.getByText("v0.1.0")).toBeInTheDocument();
    });
  });

  it("renders error state when backend is unreachable", async () => {
    vi.mocked(apiClient.getHealth).mockRejectedValueOnce(
      new Error("Network Error: Connection refused")
    );

    render(
      <Providers>
        <HomePage />
      </Providers>
    );

    await waitFor(() => {
      expect(
        screen.getByText("Backend Unreachable or Health Check Failed")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Network Error: Connection refused")
      ).toBeInTheDocument();
    });
  });
});
