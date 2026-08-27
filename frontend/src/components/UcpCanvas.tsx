import type { AlertItem, UcpDocument, UcpWidget } from "../types";
import { PlotPanel } from "./PlotPanel";

function Kpi({ widget }: { widget: UcpWidget }) {
  return (
    <article className="kpi">
      <p className="kpi-label">{widget.title}</p>
      <p className="kpi-value">{widget.value}</p>
      {widget.hint && <p className="kpi-hint">{widget.hint}</p>}
    </article>
  );
}

function EvidenceBlock({ alert }: { alert?: AlertItem }) {
  if (!alert) return <p className="muted">Sin alerta asociada.</p>;
  return (
    <article className="evidence">
      <header>
        <strong>{alert.id}</strong> · {alert.patient_id} · {alert.level}
      </header>
      <p>{alert.title}</p>
      <ul>
        {alert.evidence.map((e, i) => (
          <li key={i}>
            <code>{e.variable}</code> ({e.source}, {e.window}): {e.detail}
          </li>
        ))}
      </ul>
    </article>
  );
}

export function UcpCanvas({ doc }: { doc: UcpDocument }) {
  const kpis = doc.widgets.filter((w) => w.type === "kpi");
  const rest = doc.widgets.filter((w) => w.type !== "kpi");
  return (
    <section className="ucp">
      <header className="ucp-head">
        <p className="eyebrow">UCP v1.0</p>
        <h2>{doc.title}</h2>
        {doc.subtitle && <p className="muted">{doc.subtitle}</p>}
      </header>
      {kpis.length > 0 && (
        <div className="kpi-grid">
          {kpis.map((w, i) => (
            <Kpi key={w.id || i} widget={w} />
          ))}
        </div>
      )}
      {rest.map((w, i) => {
        if (w.type === "alert_list") {
          return (
            <div key={w.id || i} className="ucp-block">
              <h3>{w.title || "Alertas"}</h3>
              <ul className="plain">
                {(w.items || []).map((a) => (
                  <li key={a.id}>
                    <b className={`lvl ${a.level}`}>{a.level}</b> {a.patient_id} — {a.title}
                  </li>
                ))}
              </ul>
            </div>
          );
        }
        if (w.type === "evidence") {
          return (
            <div key={w.id || i} className="ucp-block">
              <h3>{w.title || "Evidencia"}</h3>
              <EvidenceBlock alert={w.alert} />
            </div>
          );
        }
        if (w.type === "chart" && w.plotly) {
          return (
            <div key={w.id || i} className="ucp-block">
              <h3>{w.title || "Gráfico"}</h3>
              <PlotPanel spec={w.plotly} />
            </div>
          );
        }
        if (w.type === "markdown") {
          return (
            <p key={w.id || i} className="muted">
              {w.text}
            </p>
          );
        }
        if (w.type === "table") {
          const rows = w.rows || [];
          const keys = rows[0] ? Object.keys(rows[0]) : [];
          return (
            <div key={w.id || i} className="ucp-block table-wrap">
              <h3>{w.title || "Tabla"}</h3>
              <table>
                <thead>
                  <tr>
                    {keys.map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, ri) => (
                    <tr key={ri}>
                      {keys.map((k) => (
                        <td key={k}>{String(row[k])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return null;
      })}
    </section>
  );
}
