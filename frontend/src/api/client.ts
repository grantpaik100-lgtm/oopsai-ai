import type {
  AnalyzeRequest,
  AnalyzeResponse,
  CaseStartRequest,
  CaseStartResponse,
  DbSummary,
  GenerateActionImageRequest,
  GenerateActionImageResponse,
  NormalizeRequest,
  NormalizedInput,
  SimilarCase,
} from "../types/api";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch (networkError) {
    throw new Error(`네트워크 오류 — 백엔드(${url})에 연결할 수 없습니다.`);
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // body가 JSON이 아닌 경우 무시
    }
    throw new Error(`${response.status} ${detail || response.statusText} (${url})`);
  }

  return response.json() as Promise<T>;
}

export function startCase(request: CaseStartRequest): Promise<CaseStartResponse> {
  return requestJson<CaseStartResponse>("/api/cases/start", {
    method: "POST",
    body: JSON.stringify(request),
  });
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

export function generateActionImage(
  request: GenerateActionImageRequest,
): Promise<GenerateActionImageResponse> {
  return requestJson<GenerateActionImageResponse>("/api/generate-action-image", {
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
