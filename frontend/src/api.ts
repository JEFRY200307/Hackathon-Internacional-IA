import type { AlertItem, AssistantMessage, PlotlySpec, UcpDocument } from "./types";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function parse<T>(res: Promise<Response>): Promise<T> {
  const resolved = await res;
  if (!resolved.ok) {
    const text = await resolved.text();
    throw new Error(text || resolved.statusText);
  }
  return resolved.json() as Promise<T>;
}

export const api = {
  health: () => parse<{ ok: boolean; llm: string; model: string; dataset: string; alerts: number; pretrained: { mode: string } }>(
    fetch(`${API}/api/health`),
  ),
  alerts: (level?: string) =>
    parse<{ items: AlertItem[]; counts: Record<string, number>; origin: string }>(
      fetch(`${API}/api/alerts${level ? `?level=${level}` : ""}`),
    ),
  review: (id: string, status: string) =>
    parse<AlertItem>(
      fetch(`${API}/api/alerts/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }),
    ),
  turno: () => parse<UcpDocument>(fetch(`${API}/api/dashboards/turno`)),
  chat: (messages: { role: string; content: string }[]) =>
    parse<{ message: AssistantMessage }>(
      fetch(`${API}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages }),
      }),
    ),
  chart: (patientId: string, variables: string[]) =>
    parse<PlotlySpec>(
      fetch(`${API}/api/charts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId, variables, kind: "line" }),
      }),
    ),
  predict: (patientId: string) =>
    parse<Record<string, unknown>>(
      fetch(`${API}/api/model/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId }),
      }),
    ),
};
