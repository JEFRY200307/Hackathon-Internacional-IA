// Paleta validada (dataviz skill: color-formula.md + palette.md), fijada por
// identidad — nunca por orden — para que un filtro no repinte lo que sobrevive.

export const VARIABLE_COLORS: Record<string, string> = {
  heart_rate: "#2a78d6", // categórico slot 1 · azul
  sbp: "#eb6834", // slot 2 · naranja
  resp_rate: "#1baf7a", // slot 3 · aqua
  temp: "#eda100", // slot 4 · amarillo
  dbp: "#e87ba4", // slot 5 · magenta
  spo2: "#4a3aa7", // slot 7 · violeta
  LAB_A: "#008300", // slot 6 · verde
  LAB_B: "#e34948", // slot 8 · rojo
  LAB_C: "#4a3aa7",
  LAB_D: "#e87ba4",
};

export function colorFor(variable: string): string {
  return VARIABLE_COLORS[variable] || "#52514e";
}

// Paleta de estado (fija, nunca temática) para el nivel de prioridad de una
// alerta — ordinal de severidad, siempre acompañada del texto del nivel.
export const LEVEL_COLORS: Record<string, string> = {
  CRITICO: "#d03b3b",
  ALTO: "#ec835a",
  MEDIO: "#fab219",
  BAJO: "#64748b",
  DESCARTADO: "#0ca30c",
};
