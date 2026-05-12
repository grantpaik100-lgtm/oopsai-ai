import type {
  AnalyzeRequest,
  AnalyzeResponse,
  DbSummary,
  NormalizeRequest,
  NormalizedInput,
  SimilarCase,
} from "../types/api";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = `API 요청 실패 (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep the status-based message when the response body is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function normalizeIncident(request: NormalizeRequest): Promise<NormalizedInput> {
  return requestJson<NormalizedInput>("/api/normalize", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function analyzeIncident(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  return requestJson<AnalyzeResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function fetchDbSummary(): Promise<DbSummary> {
  return requestJson<DbSummary>("/dev/db-summary");
}

export function fetchSimilarCases(type?: string, hazard?: string): Promise<SimilarCase[]> {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (hazard) params.set("hazard", hazard);
  const query = params.toString();
  return requestJson<SimilarCase[]>(`/api/cases/similar${query ? `?${query}` : ""}`);
}
