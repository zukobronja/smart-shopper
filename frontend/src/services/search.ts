import { SearchRequestPayload, SearchResponse } from "../types/search";
import { buildUrl } from "./http";

export async function searchProducts(payload: SearchRequestPayload, signal?: AbortSignal): Promise<SearchResponse> {
  const response = await fetch(buildUrl("/v1/search"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
    credentials: "include",
  });

  if (!response.ok) {
    let errorMessage = `Search failed with status ${response.status}`;
    try {
      const errorBody = await response.json();
      if (errorBody?.detail) {
        if (Array.isArray(errorBody.detail)) {
          errorMessage = errorBody.detail
            .map((entry: unknown) => {
              if (typeof entry === "object" && entry !== null && "msg" in entry) {
                const candidate = (entry as { msg?: unknown }).msg;
                return candidate ? String(candidate) : "";
              }
              return entry ? String(entry) : "";
            })
            .filter((text: string) => text.length > 0)
            .join(", ");
        } else {
          errorMessage = String(errorBody.detail);
        }
      }
    } catch (_err) {
      // Ignore JSON parse issues
    }
    throw new Error(errorMessage);
  }

  const data = (await response.json()) as SearchResponse;
  return data;
}

export async function fetchSearchRun(runId: string, signal?: AbortSignal): Promise<SearchResponse> {
  const response = await fetch(buildUrl(`/v1/search/${runId}`), {
    method: "GET",
    credentials: "include",
    signal,
  });

  if (!response.ok) {
    let errorMessage = `Failed to load search run (status ${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) {
        errorMessage = Array.isArray(body.detail)
          ? body.detail.map((entry: unknown) => (typeof entry === "string" ? entry : "")).join(", ") || errorMessage
          : String(body.detail);
      }
    } catch (_err) {
      // Ignore JSON parse errors
    }
    throw new Error(errorMessage);
  }

  return (await response.json()) as SearchResponse;
}
