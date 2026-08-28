import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";

import { SparklineChart } from "./components/SparklineChart";
import type { AlertItem, AssistantMessage, PlotlySpec, PatientDemographic } from "./types";

type Turn = { role: "user"; content: string } | (AssistantMessage & { role: "assistant" });

interface HealthInfo {
  dataset: string;
  llm: string;
  model: string;
  pretrainedMode: string;
}

export default function App() {
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [demographics, setDemographics] = useState<Record<string, PatientDemographic>>({});
  const [selected, setSelected] = useState<AlertItem | null>(null);
  
  const [turns, setTurns] = useState<Turn[]>([
    {
      role: "assistant",
      content:
        "Soy VitalSense Copilot. Puedo conversar sobre RISA Data V1.0, armar un dashboard UCP, graficar series y citar la evidencia RAG. No diagnostico.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const [error, setError] = useState<string | null>(null);
  
  // Sparkline data state
  const [patientChartSpec, setPatientChartSpec] = useState<PlotlySpec | null>(null);

  const visible = useMemo(() => {
    let list = alerts;
    if (filter) {
      list = list.filter((a) => a.level === filter);
    }
    if (search.trim()) {
      const query = search.trim().toLowerCase();
      list = list.filter((a) => a.patient_id.toLowerCase().includes(query));
    }
    return list;
  }, [alerts, filter, search]);

  // Auto-select first patient if selection is invalid or empty
  useEffect(() => {
    if (visible.length > 0) {
      const stillVisible = visible.some((a) => a.id === selected?.id);
      if (!stillVisible) {
        setSelected(visible[0]);
      }
    } else {
      setSelected(null);
    }
  }, [visible, selected]);

  async function refreshAlerts() {
    const data = await api.alerts();
    setAlerts(data.items);
    setCounts(data.counts);
  }

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealthInfo({
          dataset: h.dataset,
          llm: h.llm,
          model: h.model,
          pretrainedMode: h.pretrained.mode,
        });
      })
      .catch(() => setHealthInfo(null));
    
    refreshAlerts().catch((e) => setError(String(e)));
    
    api.patients().then((data) => {
      const map: Record<string, PatientDemographic> = {};
      for (const p of data.items) {
        map[p.patient_id] = p;
      }
      setDemographics(map);
    }).catch(() => undefined);


  }, []);

  // Fetch selected patient's 4 main signals for the sparklines
  useEffect(() => {
    if (selected) {
      api.chart(selected.patient_id, ["heart_rate", "spo2", "resp_rate", "LAB_C"])
        .then(setPatientChartSpec)
        .catch(() => setPatientChartSpec(null));
    } else {
      setPatientChartSpec(null);
    }
  }, [selected]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    setBusy(true);
    setError(null);
    const nextTurns: Turn[] = [...turns, { role: "user", content }];
    setTurns(nextTurns);
    setInput("");
    try {
      const history = nextTurns.map((t) => ({ role: t.role, content: t.content }));
      const { message } = await api.chat(history);
      setTurns([...nextTurns, { ...message, role: "assistant" }]);

    } catch (e) {
      setError(e instanceof Error ? e.message : "falló el chat");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  async function mark(status: string) {
    if (!selected) return;
    await api.review(selected.id, status);
    await refreshAlerts();
    setSelected((s) => (s ? { ...s, review_status: status } : s));
  }

  function handleCiteClick(c: any) {
    if (c.kind === "alert") {
      const alertId = c.source_id.split(":")[1];
      const alertItem = alerts.find((a) => a.id === alertId);
      if (alertItem) {
        setSelected(alertItem);
      }
    } else if (c.kind === "patient" && c.patient_id) {
      const alertItem = alerts.find((a) => a.patient_id === c.patient_id);
      if (alertItem) {
        setSelected(alertItem);
      }
    } else if (c.kind === "variable") {
      const patientId = selected?.patient_id || c.patient_id;
      if (patientId) {
        const alertItem = alerts.find((a) => a.patient_id === patientId);
        if (alertItem) setSelected(alertItem);
      }
    }
  }

  // Helper variables for selected patient
  const selectedDemo = selected ? demographics[selected.patient_id] : null;
  const sexLabel = selectedDemo?.sex_at_birth === "M" ? "Masculino" : (selectedDemo?.sex_at_birth === "F" ? "Femenino" : selectedDemo?.sex_at_birth || "N/D");
  const ageLabel = selectedDemo?.age_years ? `${selectedDemo.age_years} años` : "N/D";
  const internalId = selectedDemo?.patient_id ? `RISA-000${selectedDemo.patient_id.split("-")[1]}` : "";

  // Risk scores calculations for composition
  const riskPct = selected?.risk_score !== undefined ? Math.round(selected.risk_score * 100) : 0;
  const confidencePct = selected && selected.features?.quality_median !== undefined
    ? Math.round((0.6 + 0.4 * selected.features.quality_median) * 100)
    : 93;
  const patternName = selected ? selected.pattern.replace(/_/g, " ").toLowerCase() : "N/D";

  const compositionPattern = selected && selected.pattern_score !== undefined
    ? Math.round(selected.pattern_score * 100)
    : 80;
  const compositionAnomaly = selected && selected.anomaly_score !== undefined
    ? Math.round(selected.anomaly_score * 100)
    : 75;
  const compositionContext = selected && selected.features
    ? Math.round(((selected.features.sleep_frac || 0) * 0.5 + (selected.features.activity_frac || 0) * 0.5) * 100) || 60
    : 60;
  const compositionQuality = selected && selected.features?.quality_median !== undefined
    ? Math.round(selected.features.quality_median * 100)
    : 85;

  // Extracting sparkline trace data
  const hrTrace = patientChartSpec?.data?.find((t: any) => t.name === "heart_rate") as any;
  const spo2Trace = patientChartSpec?.data?.find((t: any) => t.name === "spo2") as any;
  const rrTrace = patientChartSpec?.data?.find((t: any) => t.name === "resp_rate") as any;
  const labTrace = patientChartSpec?.data?.find((t: any) => t.name?.startsWith("LAB_")) as any;

  const hrValue = hrTrace?.y ? `${Number(hrTrace.y[hrTrace.y.length - 1]).toFixed(2)} lpm` : "N/D";
  const spo2Value = spo2Trace?.y ? `${Number(spo2Trace.y[spo2Trace.y.length - 1]).toFixed(2)} %` : "N/D";
  const rrValue = rrTrace?.y ? `${Number(rrTrace.y[rrTrace.y.length - 1]).toFixed(2)} rpm` : "N/D";
  const labName = labTrace?.name || "Laboratorio";
  const labValue = labTrace?.y ? `${Number(labTrace.y[labTrace.y.length - 1]).toFixed(2)} u/mL` : "N/D";

  // Dynamic Suggestion Chips
  const suggestionChips = [
    "¿A quién debo revisar primero?",
    selected ? `¿Por qué ${selected.patient_id} es crítico?` : "¿Por qué es crítico?",
    selected ? `Genera dashboard de ${selected.patient_id}` : "Genera dashboard del paciente",
  ];

  const quickSuggestions = [
    "Comparar con línea base",
    "Mostrar correlaciones",
    "Explicar contribuciones del modelo",
  ];

  // Helper for evidence icon
  function getEvidenceIcon(variable: string): string {
    const v = variable.toLowerCase();
    if (v === "heart_rate") return "❤️";
    if (v === "spo2") return "💧";
    if (v === "resp_rate") return "🫁";
    if (v === "temp") return "🌡️";
    if (v.startsWith("sbp") || v.startsWith("dbp")) return "🩺";
    if (v.startsWith("lab_")) return "🧪";
    return "📋";
  }

  return (
    <div className="app">

      {/* Top Header */}
      <header className="header">
        <div className="header-left" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <img src="/logo.png" alt="VitalSense Logo" style={{ height: "42px", width: "auto" }} />
          <span style={{ borderLeft: "1px solid var(--line)", paddingLeft: "12px", marginLeft: "4px", color: "var(--muted)", fontSize: "0.85rem", fontWeight: 500 }}>
            Centro de monitoreo clínico
          </span>
        </div>
        <div className="header-right">
          <span className="header-status-indicator"></span>
          Sistema activo &nbsp; · &nbsp; Actualizado: 20:47 &nbsp; · &nbsp; 
          {healthInfo ? (
            <span className="header-metadata">
              Origen: <strong className="header-tag">{healthInfo.dataset}</strong> &nbsp; | &nbsp; 
              Copilot: <strong className="header-tag">{healthInfo.llm === "openai" ? `OpenAI (${healthInfo.model})` : "Mock Engine (Local)"}</strong> &nbsp; | &nbsp; 
              Modelo ML: <strong className="header-tag">{healthInfo.pretrainedMode === "remote" ? "Modelo Remoto (HTTP)" : "Fallback Local (v0.1)"}</strong>
            </span>
          ) : (
            <span className="header-metadata">Conectando al servidor...</span>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <section className="content">
        
        {/* Alert summary counters */}
        <div className="alert-summary">
          <div 
            className={`summary-card critical ${filter === "CRITICO" ? "active" : ""}`}
            onClick={() => setFilter(filter === "CRITICO" ? "" : "CRITICO")}
            style={{ cursor: "pointer" }}
          >
            <small>CRÍTICO</small>
            <strong>{counts["CRITICO"] || 0}</strong>
            <p>Acción inmediata</p>
          </div>
          <div 
            className={`summary-card alto ${filter === "ALTO" ? "active" : ""}`}
            onClick={() => setFilter(filter === "ALTO" ? "" : "ALTO")}
            style={{ cursor: "pointer" }}
          >
            <small>ALTO</small>
            <strong>{counts["ALTO"] || 0}</strong>
            <p>Revisar prioridad</p>
          </div>
          <div 
            className={`summary-card medio ${filter === "MEDIO" ? "active" : ""}`}
            onClick={() => setFilter(filter === "MEDIO" ? "" : "MEDIO")}
            style={{ cursor: "pointer" }}
          >
            <small>MEDIO</small>
            <strong>{counts["MEDIO"] || 0}</strong>
            <p>Monitoreo activo</p>
          </div>
          <div 
            className={`summary-card bajo ${filter === "BAJO" ? "active" : ""}`}
            onClick={() => setFilter(filter === "BAJO" ? "" : "BAJO")}
            style={{ cursor: "pointer" }}
          >
            <small>BAJO</small>
            <strong>{counts["BAJO"] || 0}</strong>
            <p>Estables</p>
          </div>
          <div 
            className="summary-card total"
            onClick={() => setFilter("")}
            style={{ cursor: "pointer" }}
          >
            <small>PACIENTES ANALIZADOS</small>
            <strong>{alerts.length}</strong>
            <p>Total seguimiento</p>
          </div>
        </div>

        {/* 3-Column main layout */}
        <div className="layout">
          
          {/* Column 1: Patient List */}
          <section className="patients">
            <h3>Pacientes prioritarios</h3>
            <input 
              placeholder="Buscar paciente o ID"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className="patient-filters">
              <button className={filter === "" ? "active todos" : ""} onClick={() => setFilter("")}>Todos</button>
              <button className={filter === "CRITICO" ? "active critico" : ""} onClick={() => setFilter("CRITICO")}>Crítico</button>
              <button className={filter === "ALTO" ? "active alto" : ""} onClick={() => setFilter("ALTO")}>Alto</button>
              <button className={filter === "MEDIO" ? "active medio" : ""} onClick={() => setFilter("MEDIO")}>Medio</button>
              <button className={filter === "BAJO" ? "active bajo" : ""} onClick={() => setFilter("BAJO")}>Bajo</button>
              <button className={filter === "DESCARTADO" ? "active descartado" : ""} onClick={() => setFilter("DESCARTADO")}>Descartado</button>
            </div>
            <div className="patient-list">
              {visible.map((a) => (
                <button 
                  key={a.id}
                  className={`patient-card ${a.level.toLowerCase()} ${selected?.id === a.id ? "selected" : ""}`}
                  onClick={() => setSelected(a)}
                >
                  <div className="patient-card-header">
                    <b>{a.patient_id}</b>
                    <span>{a.risk_score !== undefined ? Math.round(a.risk_score * 100) : 0}%</span>
                  </div>
                  <p>{a.level}</p>
                  <small>
                    {a.evidence.map(e => e.variable).slice(0, 3).join(" ↑ · ")}
                  </small>
                </button>
              ))}
            </div>
          </section>

          {/* Column 2: Clinical patient view (Center) */}
          <main className="patient-view">
            {selected && (
              <>
                <div className="patient-view-header">
                  <div className="patient-title-group">
                    <h1>
                      {selected.patient_id}
                      <label className={selected.level.toLowerCase()}>{selected.level}</label>
                    </h1>
                    <div className="patient-demographics">
                      {sexLabel} • {ageLabel} • ID interno: {internalId}
                    </div>
                  </div>
                  <div className="patient-time-since-alert">
                    Tiempo desde alerta
                    <strong>4 min</strong>
                  </div>
                </div>

                {/* Score indicators */}
                <div className="metrics">
                  <div className="metrics-card red">
                    <small>Riesgo crítico</small>
                    <strong>{riskPct}%</strong>
                    <p>Umbral crítico: 85%</p>
                  </div>
                  <div className="metrics-card">
                    <small>Confianza del modelo</small>
                    <strong>{confidencePct}%</strong>
                    <p>Confianza alta</p>
                  </div>
                  <div className="metrics-card">
                    <small>Patrón detectado</small>
                    <strong style={{ fontSize: "1.25rem", textTransform: "capitalize", margin: "14px 0" }}>
                      {patternName}
                    </strong>
                    <p>Patrón actual</p>
                  </div>
                </div>

                {/* Sparkline trends */}
                <div>
                  <h3 className="charts-section-title">Evolución clínica (últimos 5 días)</h3>
                  <div className="charts-grid">
                    <div className="chart-card">
                      <div className="chart-card-header red">
                        <span>❤️ Frecuencia cardíaca (lpm)</span>
                        <strong>{hrValue}</strong>
                      </div>
                      <div className="chart-canvas">
                        {hrTrace?.x && hrTrace?.y && (
                          <SparklineChart x={hrTrace.x as string[]} y={hrTrace.y as number[]} color="#e53935" />
                        )}
                      </div>
                    </div>

                    <div className="chart-card">
                      <div className="chart-card-header">
                        <span>💧 Saturación de oxígeno (SpO₂ %)</span>
                        <strong>{spo2Value}</strong>
                      </div>
                      <div className="chart-canvas">
                        {spo2Trace?.x && spo2Trace?.y && (
                          <SparklineChart x={spo2Trace.x as string[]} y={spo2Trace.y as number[]} color="#2168d8" />
                        )}
                      </div>
                    </div>

                    <div className="chart-card">
                      <div className="chart-card-header purple">
                        <span>𫁛 Frecuencia respiratoria (rpm)</span>
                        <strong>{rrValue}</strong>
                      </div>
                      <div className="chart-canvas">
                        {rrTrace?.x && rrTrace?.y && (
                          <SparklineChart x={rrTrace.x as string[]} y={rrTrace.y as number[]} color="#8b5cf6" />
                        )}
                      </div>
                    </div>

                    <div className="chart-card">
                      <div className="chart-card-header green">
                        <span>🧪 {labName} (u/mL)</span>
                        <strong>{labValue}</strong>
                      </div>
                      <div className="chart-canvas">
                        {labTrace?.x && labTrace?.y && (
                          <SparklineChart x={labTrace.x as string[]} y={labTrace.y as number[]} color="#22a06b" />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}
          </main>

          {/* Column 3: Evidence list and composition (Right) */}
          <aside className="evidence-panel">
            {selected && (
              <>
                <h2>¿Por qué está {selected.level.toLowerCase()}?</h2>
                
                <div className="composition-section">
                  <h3>Evidencias principales</h3>
                  <div className="evidence-list">
                    {selected.evidence.map((e, index) => (
                      <div key={index} className="evidence-box">
                        <span className="evidence-icon">{getEvidenceIcon(e.variable)}</span>
                        <div>
                          <strong>{e.variable.replace(/_/g, " ").toUpperCase()}</strong>
                          <div style={{ marginTop: "2px" }}>{e.detail}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="composition-section">
                  <h3>Composición del riesgo</h3>
                  
                  <div className="composition-row">
                    <span className="composition-label">Patrón</span>
                    <div className="composition-bar-wrap">
                      <div className="composition-bar" style={{ width: `${compositionPattern}%` }}></div>
                    </div>
                    <span className="composition-value">{compositionPattern}%</span>
                  </div>

                  <div className="composition-row">
                    <span className="composition-label">Anomalía</span>
                    <div className="composition-bar-wrap">
                      <div className="composition-bar purple" style={{ width: `${compositionAnomaly}%` }}></div>
                    </div>
                    <span className="composition-value">{compositionAnomaly}%</span>
                  </div>

                  <div className="composition-row">
                    <span className="composition-label">Contexto</span>
                    <div className="composition-bar-wrap">
                      <div className="composition-bar green" style={{ width: `${compositionContext}%` }}></div>
                    </div>
                    <span className="composition-value">{compositionContext}%</span>
                  </div>

                  <div className="composition-row">
                    <span className="composition-label">Calidad de datos</span>
                    <div className="composition-bar-wrap">
                      <div className="composition-bar red" style={{ width: `${compositionQuality}%` }}></div>
                    </div>
                    <span className="composition-value">{compositionQuality}%</span>
                  </div>
                </div>

                <div className="actions-list">
                  <button className="btn-primary" onClick={() => void send(`Genera dashboard de ${selected.patient_id}`)}>
                    Ver evidencia
                  </button>
                  <button className="btn-secondary" onClick={() => void mark(selected.review_status === "revisada" ? "abierta" : "revisada")}>
                    {selected.review_status === "revisada" ? "Revertir a abierta" : "Marcar revisada"}
                  </button>
                  <button className="btn-outline">Comparar paciente</button>
                </div>
              </>
            )}
          </aside>
        </div>


        {/* Floating Chat Launcher Button */}
        {!chatOpen && (
          <button className="chat-launcher-btn" onClick={() => setChatOpen(true)}>
            💬 <b>VitalSense Copilot</b>
          </button>
        )}

        {/* Floating VitalSense Copilot chat widget */}
        {chatOpen && (
          <footer className="footer-copilot-floating">
            <div className="copilot-header">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span>◉</span> <b>VitalSense Copilot</b> <label>Beta</label>
              </div>
              <button className="copilot-close-btn" onClick={() => setChatOpen(false)}>✕</button>
            </div>

            <div className="copilot-main-vertical">
              <div className="copilot-thread">
                {turns.map((t, i) => (
                  <article key={i} className={`copilot-bubble ${t.role}`}>
                    <p>{t.content}</p>
                    {t.role === "assistant" && t.citations && t.citations.length > 0 && (
                      <div className="cites">
                        {t.citations.map((c) => (
                          <details key={c.source_id}>
                            <summary style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span>{c.source_id} - {c.title}</span>
                              {(c.patient_id || (c.kind === "variable" && selected)) && (
                                <button
                                  type="button"
                                  className="cite-action-btn"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleCiteClick(c);
                                  }}
                                >
                                  📊 Ver en Canvas
                                </button>
                              )}
                            </summary>
                            <pre>{c.snippet}</pre>
                          </details>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
              </div>

              {/* Suggestions chips */}
              <div className="chips">
                {suggestionChips.map((p) => (
                  <button key={p} disabled={busy} onClick={() => void send(p)}>
                    {p}
                  </button>
                ))}
              </div>

              {/* Text composer */}
              <form onSubmit={onSubmit} className="copilot-input-bar">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Pregúntame sobre patrones, evidencia..."
                  disabled={busy}
                />
                <button type="submit" disabled={busy}>
                  {busy ? "…" : "Enviar"}
                </button>
              </form>
              {error && <p className="error">{error}</p>}

              {/* Quick Suggestions section inside card */}
              <div className="quick-suggestions-section">
                <h4>Sugerencias rápidas</h4>
                <div className="quick-suggestions-links">
                  {quickSuggestions.map((s) => (
                    <button 
                      key={s}
                      className="suggestion-link"
                      disabled={busy}
                      onClick={() => void send(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </footer>
        )}

      </section>
    </div>
  );
}
