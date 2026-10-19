import { components } from "./api-types";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type CorridorResponse = components["schemas"]["CorridorResponse"];
export type CorridorDetailResponse = components["schemas"]["CorridorDetailResponse"];
export type SectionResponse = components["schemas"]["SectionResponse"];
export type TaskResponse = components["schemas"]["TaskResponse"];
export type TaskCreate = components["schemas"]["TaskCreate"];
export type TaskUpdate = components["schemas"]["TaskUpdate"];
export type TrainSlotResponse = components["schemas"]["TrainSlotResponse"];
export type BlockWindowResponse = components["schemas"]["BlockWindowResponse"];
export type ResourceResponse = components["schemas"]["ResourceResponse"];
export type SeedResponse = components["schemas"]["SeedResponse"];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API Error [${response.status}] ${url}: ${errorBody}`);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getCorridors(): Promise<CorridorResponse[]> {
  return request<CorridorResponse[]>("/api/corridors");
}

export async function getCorridor(id: string): Promise<CorridorDetailResponse> {
  return request<CorridorDetailResponse>(`/api/corridors/${id}`);
}

export async function getSections(corridorId?: string): Promise<SectionResponse[]> {
  const query = corridorId ? `?corridor_id=${encodeURIComponent(corridorId)}` : "";
  return request<SectionResponse[]>(`/api/sections${query}`);
}

export async function getTasks(params?: {
  department?: string;
  sectionId?: string;
  status?: string;
}): Promise<TaskResponse[]> {
  const searchParams = new URLSearchParams();
  if (params?.department) searchParams.append("department", params.department);
  if (params?.sectionId) searchParams.append("section_id", params.sectionId);
  if (params?.status) searchParams.append("status", params.status);
  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<TaskResponse[]>(`/api/tasks${query}`);
}

export async function getTask(id: string): Promise<TaskResponse> {
  return request<TaskResponse>(`/api/tasks/${id}`);
}

export async function createTask(task: TaskCreate): Promise<TaskResponse> {
  return request<TaskResponse>("/api/tasks", {
    method: "POST",
    body: JSON.stringify(task),
  });
}

export async function updateTask(id: string, updates: TaskUpdate): Promise<TaskResponse> {
  return request<TaskResponse>(`/api/tasks/${id}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteTask(id: string): Promise<void> {
  await request<void>(`/api/tasks/${id}`, {
    method: "DELETE",
  });
}

export async function getTrains(params?: {
  corridorId?: string;
  sectionId?: string;
}): Promise<TrainSlotResponse[]> {
  const searchParams = new URLSearchParams();
  if (params?.corridorId) searchParams.append("corridor_id", params.corridorId);
  if (params?.sectionId) searchParams.append("section_id", params.sectionId);
  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<TrainSlotResponse[]>(`/api/trains${query}`);
}

export async function getWindows(params?: {
  sectionId?: string;
  isNightWindow?: boolean;
}): Promise<BlockWindowResponse[]> {
  const searchParams = new URLSearchParams();
  if (params?.sectionId) searchParams.append("section_id", params.sectionId);
  if (params?.isNightWindow !== undefined) {
    searchParams.append("is_night_window", String(params.isNightWindow));
  }
  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<BlockWindowResponse[]>(`/api/windows${query}`);
}

export async function getResources(department?: string): Promise<ResourceResponse[]> {
  const query = department ? `?department=${encodeURIComponent(department)}` : "";
  return request<ResourceResponse[]>(`/api/resources${query}`);
}

export async function triggerSeed(seed: number = 42, reset: boolean = true): Promise<SeedResponse> {
  return request<SeedResponse>("/api/seed", {
    method: "POST",
    body: JSON.stringify({ seed, reset }),
  });
}
