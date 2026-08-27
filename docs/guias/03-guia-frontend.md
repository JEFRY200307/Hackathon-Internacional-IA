# Guía — Frontend: sistema de diseño

Fondo blanco, paleta clínica de confianza, y colores de severidad que se validaron con la skill `dataviz` (`node scripts/validate_palette.js`) en vez de elegirse a ojo — ver el reporte de validación en el historial del PR. Todo vive en `frontend/src/index.css` (tokens de UI) y `frontend/src/palette.ts` (colores de series/estado).

## 1. Tokens de color (`index.css`, `:root`)

| Token | Valor | Uso |
| --- | --- | --- |
| `--paper` | `#ffffff` | Fondo principal de la app (requisito: "background blanco") |
| `--panel` | `#f9f9f7` | Paneles secundarios (rail de alertas, canvas) |
| `--surface` | `#fcfcfb` | Superficie de tarjetas dentro de un panel (KPIs) |
| `--ink` / `--ink-secondary` / `--muted` | `#0b0b0b` / `#52514e` / `#898781` | Jerarquía de texto — nunca un color de marca para texto de lectura |
| `--accent` | `#2a78d6` | Acciones primarias, foco, filtro activo — es el mismo azul que identifica `heart_rate` en los gráficos (coherencia de marca) |
| `--line` | `#e1e0d9` | Bordes y separadores |

## 2. Paleta de severidad (`palette.ts`, `LEVEL_COLORS`)

Ordinal, de mayor a menor prioridad — **siempre como fondo de una pill/badge con el texto del nivel dentro**, nunca como color de texto plano sobre blanco: dos de los cinco tonos (`ALTO`, `MEDIO`) no alcanzan 3:1 de contraste como texto, así que la mitigación (etiqueta visible, nunca color solo) es obligatoria, no opcional. Ver `.lvl` en `index.css`.

| Nivel | Color | Lectura |
| --- | --- | --- |
| `CRITICO` | `#d03b3b` | Revisar ahora |
| `ALTO` | `#ec835a` | Prioridad alta |
| `MEDIO` | `#fab219` | Seguimiento |
| `BAJO` | `#64748b` | Bajo (neutro) |
| `DESCARTADO` | `#0ca30c` | Descartado con motivo visible (RN-02: nunca se oculta del todo) |

## 3. Paleta de series (`palette.ts`, `VARIABLE_COLORS`)

Color por **identidad de variable**, fijo, nunca por orden de aparición — si un filtro cambia qué series se muestran, las que quedan no cambian de color. `heart_rate` siempre es azul, `spo2` siempre violeta, `LAB_A` siempre verde, etc., en cualquier gráfico de la app (`PlotPanel.tsx` aplica `colorFor(variable)` a cada trace antes de pintar).

## 4. Componentes

- **Badge de nivel** (`.lvl`): pill con `border-radius: 999px`, fondo del color de severidad, texto corto en mayúsculas. Nunca aparece sin el texto del nivel al lado o dentro.
- **Tarjeta de alerta** (`.alert-card`): borde neutro, se resalta con `--accent` al seleccionar — el color de severidad vive solo en el badge interno, no en el borde de la tarjeta completa (evita que el color domine la jerarquía visual sobre el contenido).
- **Gráficos** (`PlotPanel.tsx`): fondo `#fcfcfb` (no blanco puro, para que se distinga sutilmente del `--paper` de la página), grid en `#e1e0d9`, líneas de 2px con marcador — nunca relleno de área por defecto (evita sugerir volumen/acumulación donde el dato es una serie puntual).
- **Chat** (`.bubble`): burbuja de usuario en un azul muy claro (`#eaf1fb`) derivado de `--accent`, nunca el mismo `--accent` sólido (reservado para acciones).

## 5. Tipografía

`system-ui, -apple-system, "Segoe UI", sans-serif` en toda la app — sin fuente de marca custom, para no sumar una descarga de fuente a un prototipo que ya carga Plotly (~1.4 MB gzip). `font-variant-numeric: tabular-nums` en valores de KPI para que los dígitos no salten al actualizar.

## 6. Accesibilidad

- Todo nivel de severidad lleva texto, nunca solo color (punto 2).
- Foco visible: `.composer input:focus` usa `outline`, no `outline: none`.
- Contraste de texto de lectura (`--ink` sobre `--paper`) es 19.6:1 — muy por encima del mínimo WCAG AA (4.5:1).
- La app no tiene modo oscuro: es una decisión explícita (no una omisión) para un panel clínico de uso diurno en un turno de trabajo; si se agrega en el futuro, debe ser un tema *seleccionado* con sus propios pasos de validación (`dataviz` skill), no un `prefers-color-scheme` automático sobre estos mismos tokens.
