import type { AlertItem, RisaUiDocument, RisaUiProvenance, RisaUiWidget } from "../types";
import { PlotPanel } from "./PlotPanel";

function Provenance({ value }: { value?: RisaUiProvenance }) {
  if (!value) return null;
  return (
    <p className="risa-ui-provenance">
      Fuente: {value.source}
      {typeof value.count === "number" ? ` · ${value.count} registros` : ""}
      {value.metric ? ` · ${value.metric}` : ""}
    </p>
  );
}

function Kpi({ widget }: { widget: Extract<RisaUiWidget, { type: "kpi" }> }) {
  return (
    <article className="kpi">
      <p className="kpi-label">{widget.title}</p>
      <p className="kpi-value">{widget.value}</p>
      {widget.hint && <p className="kpi-hint">{widget.hint}</p>}
      {widget.detail && <p className="kpi-detail">{widget.detail}</p>}
      <Provenance value={widget.provenance} />
    </article>
  );
}

function EvidenceBlock({ alert, emptyMessage }: { alert?: AlertItem; emptyMessage?: string }) {
  if (!alert) return <p className="muted">{emptyMessage || "Sin alerta asociada."}</p>;
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

type Props = {
  doc: RisaUiDocument;
  onSelectAlert?: (alertId: string) => void;
};

export function RisaUiCanvas({ doc, onSelectAlert }: Props) {
  const kpis = doc.widgets.filter(
    (widget): widget is Extract<RisaUiWidget, { type: "kpi" }> => widget.type === "kpi",
  );
  const rest = doc.widgets.filter((widget) => widget.type !== "kpi");
  return (
    <section className="risa-ui">
      <header className="risa-ui-head">
        <p className="eyebrow">RISA UI Protocol v1.0</p>
        <h2>{doc.title}</h2>
        {doc.subtitle && <p className="muted">{doc.subtitle}</p>}
      </header>
      {kpis.length > 0 && (
        <div className="kpi-grid">
          {kpis.map((widget) => (
            <Kpi key={widget.id} widget={widget} />
          ))}
        </div>
      )}
      {rest.map((widget) => {
        if (widget.type === "alert_list") {
          const interactive = widget.on_select?.action === "select_alert" && onSelectAlert;
          return (
            <div key={widget.id} className="risa-ui-block">
              <h3>{widget.title || "Alertas"}</h3>
              {(widget.items || []).length ? (
                <ul className="plain risa-ui-alerts">
                  {(widget.items || []).map((alert) => (
                    <li key={alert.id}>
                      <button
                        type="button"
                        disabled={!interactive}
                        onClick={() => interactive && onSelectAlert(alert.id)}
                      >
                        <b className={`lvl ${alert.level}`}>{alert.level}</b> {alert.patient_id} — {alert.title}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">{widget.empty_message || "Sin alertas."}</p>
              )}
              <Provenance value={widget.provenance} />
            </div>
          );
        }
        if (widget.type === "evidence") {
          return (
            <div key={widget.id} className="risa-ui-block">
              <h3>{widget.title || "Evidencia"}</h3>
              <EvidenceBlock alert={widget.alert} emptyMessage={widget.empty_message} />
              <Provenance value={widget.provenance} />
            </div>
          );
        }
        if (widget.type === "chart") {
          return (
            <div key={widget.id} className="risa-ui-block">
              <h3>{widget.title || "Gráfico"}</h3>
              {widget.plotly ? <PlotPanel spec={widget.plotly} /> : <p className="muted">Gráfico sin hidratar.</p>}
            </div>
          );
        }
        if (widget.type === "markdown") {
          return (
            <div key={widget.id} className="risa-ui-block">
              {widget.title && <h3>{widget.title}</h3>}
              <p className="muted">{widget.text}</p>
            </div>
          );
        }
        if (widget.type === "table") {
          const rows = widget.rows || [];
          const keys = rows[0] ? Object.keys(rows[0]) : [];
          const interactive = widget.on_select?.action === "select_alert" && onSelectAlert;
          return (
            <div key={widget.id} className="risa-ui-block table-wrap">
              <h3>{widget.title || "Tabla"}</h3>
              {rows.length ? (
                <table>
                  <thead>
                    <tr>
                      {keys.map((key) => (
                        <th key={key}>{key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, rowIndex) => (
                      <tr
                        key={rowIndex}
                        className={interactive && row.id ? "interactive-row" : undefined}
                        onClick={() => interactive && row.id && onSelectAlert(String(row.id))}
                      >
                        {keys.map((key) => (
                          <td key={key}>{String(row[key] ?? "—")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">{widget.empty_message || "Sin filas."}</p>
              )}
              <Provenance value={widget.provenance} />
            </div>
          );
        }
        return null;
      })}
    </section>
  );
}
