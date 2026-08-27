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
    evidence_role?: string;
    record_id?: string;
    source_file?: string;
    contribution?: number;
  }>;
  missing_sources: string[];
  review_status: string;
  anomaly_score?: number;
  pattern_score?: number;
  risk_score?: number;
  priority_level?: string;
  model_provenance?: {
    source?: string;
    fingerprint?: string;
    anomaly_model?: string;
    pattern_model?: string;
  };
};

export type AlertSummary = Pick<
  AlertItem,
  "id" | "patient_id" | "level" | "pattern" | "title" | "score" | "risk_score" | "priority_level"
>;

export type RisaUiProvenance = {
  source: string;
  count?: number;
  metric?: string;
  scope_id?: string;
  cohort?: string;
};

type RisaUiBaseWidget = {
  id: string;
  title?: string;
  empty_message?: string;
  provenance?: RisaUiProvenance;
};

export type RisaUiWidget =
  | (RisaUiBaseWidget & {
      type: "kpi";
      metric: string;
      value: string;
      hint?: string;
      detail?: string;
    })
  | (RisaUiBaseWidget & {
      type: "chart";
      chart: {
        patient_id?: string;
        variables: string[];
        kind: "line" | "bar" | "scatter";
      };
      plotly?: PlotlySpec;
    })
  | (RisaUiBaseWidget & {
      type: "table";
      rows?: Record<string, unknown>[];
      on_select?: { action: "select_alert" };
    })
  | (RisaUiBaseWidget & {
      type: "alert_list";
      items?: AlertSummary[];
      on_select?: { action: "select_alert" };
    })
  | (RisaUiBaseWidget & {
      type: "evidence";
      alert?: AlertItem;
    })
  | (RisaUiBaseWidget & {
      type: "markdown";
      text: string;
    });

export type RisaUiDocument = {
  protocol: "risa-ui";
  version: "1.0";
  title: string;
  subtitle?: string;
  widgets: RisaUiWidget[];
};

export type PlotlySpec = {
  data: unknown[];
  layout: Record<string, unknown>;
  provenance?: Array<{
    variable?: string;
    source: string;
    n?: number;
    patient_id?: string;
    scope_id?: string;
    cohort?: string;
    patient_count?: number;
  }>;
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
  risa_ui?: RisaUiDocument | null;
  charts?: PlotlySpec[];
  degraded?: boolean;
  model?: string | null;
  query_plan?: {
    intent: string;
    wants_dashboard: boolean;
    cohorts: Array<Record<string, unknown>>;
  };
  resolved_scope?: {
    scope_id: string;
    patient_ids: string[];
    cohorts: Array<{ name: string; total: number; filters: Record<string, unknown> }>;
    warnings: string[];
  };
  warnings?: string[];
};
