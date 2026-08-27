import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { UcpCanvas } from "./components/UcpCanvas";
import { PlotPanel } from "./components/PlotPanel";
import type { AlertItem, AssistantMessage, PlotlySpec, UcpDocument } from "./types";

type Turn = { role: "user"; content: string } | (AssistantMessage & { role: "assistant" });

const PROMPTS = [
  "¿A quién debo revisar primero y por qué?",
  "Armá un dashboard del turno con UCP",
  "Graficá la FC y el marcador de laboratorio del paciente crítico",
  "¿Por qué PAT-0001 está descartado?",
  "¿Qué dice el modelo preentrenado del caso más prioritario?",
];

function format(text: string) {
  return text.split("\n").map((line, i) => <p key={i}>{line}</p>);
}

export default function App() {
  const [health, setHealth] = useState<string>("conectando…");
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<string>("");
  const [selected, setSelected] = useState<AlertItem | null>(null);
  const [turns, setTurns] = useState<Turn[]>([
    {
      role: "assistant",
      content:
        "Soy RISA Signal. Puedo conversar sobre RISA Data V1.0, armar un dashboard UCP, graficar series y citar la evidencia RAG. No diagnostico.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [ucp, setUcp] = useState<UcpDocument | null>(null);
  const [charts, setCharts] = useState<PlotlySpec[]>([]);
  const [error, setError] = useState<string | null>(null);

  const visible = useMemo(
    () => (filter ? alerts.filter((a) => a.level === filter) : alerts),
    [alerts, filter],
  );

  async function refreshAlerts() {
    const data = await api.alerts();
    setAlerts(data.items);
    setCounts(data.counts);
  }

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth(`${h.dataset} · LLM ${h.llm}/${h.model} · modelo ${h.pretrained.mode}`);
      })
      .catch(() => setHealth("backend no disponible — ¿levantaste uvicorn en :8000?"));
    refreshAlerts().catch((e) => setError(String(e)));
    api.turno().then(setUcp).catch(() => undefined);
  }, []);

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
      setTurns([...nextTurns, message]);
      if (message.ucp) setUcp(message.ucp);
      if (message.charts?.length) setCharts(message.charts);
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

  return (
    <div className="shell">
      <header className="top">
        <div>
          <p className="eyebrow">HealthSignal LATAM · RISA</p>
          <h1>RISA Signal</h1>
        </div>
        <p className="status">{health}</p>
        <p className="disclaimer">Apoyo a la revisión. No es diagnóstico ni prescripción.</p>
      </header>

      <aside className="rail">
        <h2>Alertas</h2>
        <div className="filters">
          {["", "CRITICO", "ALTO", "MEDIO", "BAJO", "DESCARTADO"].map((lvl) => (
            <button key={lvl || "all"} className={filter === lvl ? "on" : ""} onClick={() => setFilter(lvl)}>
              {lvl || "todas"} {lvl ? counts[lvl] || 0 : ""}
            </button>
          ))}
        </div>
        <ul className="alert-list">
          {visible.map((a) => (
            <li key={a.id}>
              <button className={`alert-card ${selected?.id === a.id ? "sel" : ""}`} onClick={() => setSelected(a)}>
                <span className={`lvl ${a.level}`}>{a.level}</span>
                <strong>{a.patient_id}</strong>
                <small>
                  {a.pattern} · {a.id}
                </small>
                <span>{a.title}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="chat-col">
        <div className="thread">
          {turns.map((t, i) => (
            <article key={i} className={`bubble ${t.role}`}>
              {format(t.content)}
              {t.role === "assistant" && t.citations && t.citations.length > 0 && (
                <div className="cites">
                  {t.citations.map((c) => (
                    <details key={c.source_id}>
                      <summary>{c.source_id}</summary>
                      <pre>{c.snippet}</pre>
                    </details>
                  ))}
                </div>
              )}
              {t.role === "assistant" && t.tool_trace && t.tool_trace.length > 0 && (
                <details className="trace">
                  <summary>traza tools</summary>
                  <ul>
                    {t.tool_trace.map((tr, j) => (
                      <li key={j}>
                        {tr.tool} {tr.ok ? "ok" : "fail"}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </article>
          ))}
        </div>
        <div className="chips">
          {PROMPTS.map((p) => (
            <button key={p} disabled={busy} onClick={() => void send(p)}>
              {p}
            </button>
          ))}
        </div>
        <form onSubmit={onSubmit} className="composer">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Preguntá al dataset, pedí un dashboard UCP o un gráfico…"
            disabled={busy}
          />
          <button type="submit" disabled={busy}>
            {busy ? "…" : "Enviar"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </main>

      <section className="canvas">
        {selected && (
          <article className="detail">
            <h2>
              {selected.patient_id} · {selected.level}
            </h2>
            <p>{selected.title}</p>
            <p className="muted">
              Patrón {selected.pattern} · revisión {selected.review_status} · IF local {selected.local_model_score}
            </p>
            <div className="evidence">
              <h3>Evidencia</h3>
              <ul>
                {selected.evidence.map((e, i) => (
                  <li key={i}>
                    <code>{e.variable}</code> — {e.detail}
                  </li>
                ))}
              </ul>
            </div>
            <div className="hitl">
              {["revisada", "confirmada", "descartada"].map((s) => (
                <button key={s} onClick={() => void mark(s)}>
                  {s}
                </button>
              ))}
            </div>
          </article>
        )}
        {ucp && <UcpCanvas doc={ucp} />}
        {charts.map((c, i) => (
          <PlotPanel key={i} spec={c} />
        ))}
      </section>
    </div>
  );
}
