import axios, { AxiosError } from "axios";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
export interface ApiFailure { code: string; message: string; details?: unknown; status?: number }
export const api = axios.create({ baseURL: API_BASE_URL, timeout: 60000, headers: { Accept: "application/json", "Content-Type": "application/json" } });
api.interceptors.response.use((response) => response, (error: AxiosError<{ error?: { code?: string; message?: string; details?: unknown }; detail?: string }>) => {
  const body = error.response?.data;
  return Promise.reject({ code: body?.error?.code ?? "REQUEST_FAILED", message: body?.error?.message ?? body?.detail ?? error.message ?? "Request failed", details: body?.error?.details, status: error.response?.status } satisfies ApiFailure);
});
export function getApiFailure(error: unknown): ApiFailure { return typeof error === "object" && error !== null && "message" in error ? error as ApiFailure : { code: "UNKNOWN", message: "An unexpected error occurred." }; }
