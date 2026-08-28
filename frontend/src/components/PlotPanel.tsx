import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { PlotlySpec } from "../types";
import { colorFor, LEVEL_COLORS } from "../palette";

const CHART_LAYOUT_DEFAULTS = {
  paper_bgcolor: "#fcfcfb",
  plot_bgcolor: "#fcfcfb",
  font: { color: "#0b0b0b", family: "system-ui, -apple-system, 'Segoe UI', sans-serif" },
  xaxis: { gridcolor: "#e1e0d9", linecolor: "#c3c2b7", zerolinecolor: "#e1e0d9" },
  yaxis: { gridcolor: "#e1e0d9", linecolor: "#c3c2b7", zerolinecolor: "#e1e0d9" },
};

export function PlotPanel({ spec }: { spec: PlotlySpec }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || spec.error || !spec.data?.length) return;
    const colored = (spec.data as Array<Record<string, unknown>>).map((trace) => {
      const name = typeof trace.name === "string" ? trace.name : "";
      const color = colorFor(name);
      if (trace.type === "bar") {
        const categories = Array.isArray(trace.x) ? trace.x : [];
        const semanticColors = categories.map((category) => LEVEL_COLORS[String(category).toUpperCase()]);
        const markerColor =
          semanticColors.length > 0 && semanticColors.every(Boolean) ? semanticColors : color;
        return { ...trace, marker: { color: markerColor, ...(trace.marker as object) } };
      }
      return { ...trace, line: { color, width: 2, ...(trace.line as object) }, marker: { color, size: 6, ...(trace.marker as object) } };
    });
    const layout = {
      ...CHART_LAYOUT_DEFAULTS,
      ...(spec.layout || {}),
      xaxis: { ...CHART_LAYOUT_DEFAULTS.xaxis, ...((spec.layout as Record<string, unknown>)?.xaxis as object) },
      yaxis: { ...CHART_LAYOUT_DEFAULTS.yaxis, ...((spec.layout as Record<string, unknown>)?.yaxis as object) },
    };
    Plotly.newPlot(el, colored, layout, {
      responsive: true,
      displaylogo: false,
    });
    const onResize = () => Plotly.Plots.resize(el);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      Plotly.purge(el);
    };
  }, [spec]);

  if (spec.error) {
    return <p className="muted">{spec.error}</p>;
  }

  return (
    <figure className="plot-wrap">
      <div ref={ref} className="plot" />
      {spec.provenance && spec.provenance.length > 0 && (
        <figcaption>
          {spec.provenance.map((p, index) => (
            <span key={`${p.variable || p.scope_id || "source"}-${index}`}>
              {p.variable
                ? `${p.variable} · ${p.source} · n=${p.n} · ${p.patient_id}`
                : `${p.source} · ${p.scope_id || "alcance"} · ${p.patient_count || 0} pacientes`}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}
