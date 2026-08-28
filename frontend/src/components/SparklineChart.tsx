import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

function smoothSeries(data: number[], windowSize: number = 9): number[] {
  const smoothed: number[] = [];
  for (let i = 0; i < data.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    const end = i + 1;
    const window = data.slice(start, end);
    const sum = window.reduce((a, b) => a + b, 0);
    smoothed.push(Number((sum / window.length).toFixed(3)));
  }
  return smoothed;
}

export function SparklineChart({ x, y, color }: { x: string[], y: number[], color: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !x?.length || !y?.length) return;
    
    const traces = [];
    const isDense = y.length >= 6;
    
    if (isDense) {
      // Trace 1: Faint raw points representing the actual noisy observations (dispersion)
      traces.push({
        type: "scatter",
        mode: "markers",
        name: "Dispersión",
        x,
        y,
        marker: { color, size: 3, opacity: 0.15 },
        hoverinfo: "skip" as any
      });
      
      // Trace 2: Thick smoothed trend line using a moving average
      const smoothedY = smoothSeries(y, 9);
      traces.push({
        type: "scatter",
        mode: "lines",
        name: "Tendencia",
        x,
        y: smoothedY,
        line: { color, width: 3 },
        hoverinfo: "y" as any
      });
    } else {
      // Trace for sparse data (e.g. lab results with 2 points) - no smoothing needed
      traces.push({
        type: "scatter",
        mode: "lines+markers",
        name: "Valor",
        x,
        y,
        line: { color, width: 2.5 },
        marker: { color, size: 6 },
        hoverinfo: "y" as any
      });
    }
    
    const layout = {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { t: 15, l: 45, r: 15, b: 35 },
      xaxis: { 
        showgrid: true, 
        showline: true, 
        showticklabels: true, 
        zeroline: false,
        gridcolor: "#f1f5f9",
        linecolor: "#cbd5e1",
        title: { text: "Tiempo", font: { size: 10, color: "#64748b", family: "Inter, sans-serif" } },
        tickfont: { size: 9, color: "#64748b" }
      },
      yaxis: { 
        showgrid: true, 
        showline: true, 
        showticklabels: true, 
        zeroline: false,
        gridcolor: "#f1f5f9",
        linecolor: "#cbd5e1",
        title: { text: "Valor", font: { size: 10, color: "#64748b", family: "Inter, sans-serif" } },
        tickfont: { size: 9, color: "#64748b" }
      },
      showlegend: false,
      hovermode: "x" as any
    };

    Plotly.newPlot(el, traces, layout, {
      responsive: true,
      displayModeBar: false,
    });
    
    const onResize = () => Plotly.Plots.resize(el);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      Plotly.purge(el);
    };
  }, [x, y, color]);

  return <div ref={ref} style={{ width: "100%", height: "100%" }} />;
}
