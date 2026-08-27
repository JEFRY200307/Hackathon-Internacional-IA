export type ChatRole = "user" | "assistant";

export type Citation = {
  source_id: string;
  kind: string;
  patient_id?: string | null;
  title: string;
  snippet: string;
  score?: number;
};

export type ToolTrace = {
  tool: string;
  ok: boolean;
  args?: Record<string, unknown>;
  detail?: string;
};

export type AlertItem = {
  id: string;
  patient_id: string;
  score: number;
  level: string;
  pattern: string;
  title: string;
  evidence: Array<{
    variable: string;
    source: string;
    window: string;
    detail: string;
    values: Record<string, unknown>;
  }>;
  missing_sources: string[];
  review_status: string;
  local_model_score?: number;
};

export type UcpWidget = {
  id?: string;
  type: string;
  title?: string;
  value?: string;
  hint?: string;
  text?: string;
  items?: AlertItem[];
  alert?: AlertItem;
  plotly?: PlotlySpec;
  rows?: Record<string, unknown>[];
};

export type UcpDocument = {
  protocol: string;
  version: string;
  title: string;
  subtitle?: string;
  widgets: UcpWidget[];
};

export type PlotlySpec = {
  data: unknown[];
  layout: Record<string, unknown>;
  provenance?: Array<{ variable: string; source: string; n: number; patient_id: string }>;
  error?: string;
  missing?: string[];
  origin?: string;
  patient_id?: string;
};

export type AssistantMessage = {
  role: "assistant";
  content: string;
  citations?: Citation[];
  tool_trace?: ToolTrace[];
  ucp?: UcpDocument | null;
  charts?: PlotlySpec[];
  degraded?: boolean;
  model?: string | null;
};
