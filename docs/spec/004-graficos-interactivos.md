# SPEC-004 — Chat que crea gráficos interactivos con los datos

- Estado: `aceptada`
- Área: 1 Salud
- Relaciona: RF-13, RNF-04, RN-01
- Autor: equipo
- Fecha: 2026-08-26

## Problema

La evidencia de una señal de riesgo es una evolución en el tiempo. El profesional necesita un gráfico interactivo (zoom, hover, varias series) generado desde la pregunta, no un PNG estático.

## Actor y disparador

Profesional en el chat. Dispara con “grafica la FC y SpO2 de P001”, “compara creatinina de los casos altos”, etc.

## Comportamiento esperado

1. El LLM llama `emit_chart` con `{ kind, title, patient_id?, variables[], window? }`.
2. El backend resuelve las series reales (vitales / laboratorio) y devuelve un spec Plotly (`data` + `layout`).
3. El frontend renderiza Plotly: hover, zoom, leyenda. Si hay dos variables de distinta unidad, usa eje Y secundario.
4. Debajo del gráfico se muestra la procedencia (fuente, ventana, paciente).
5. **Resultado observable:** un gráfico interactivo cuyo tooltip coincide con un timestamp del dataset.

## Entradas

- `kind`: `line` | `bar` | `scatter`.
- `patient_id` opcional; si falta, se usa el caso de mayor prioridad.
- Variables del catálogo: `heart_rate`, `spo2`, `resp_rate`, `sbp`, `temp`, `creatinine`, `wbc`, `lactate`, `glucose`.

## Salidas

- Spec Plotly hidratado + metadatos de procedencia.
- Mensaje de error claro si la variable o el paciente no existen (RF-08).

## No cubierto

- Gráficos 3D, mapas, animaciones.
- Exportación a PDF/informe clínico.
- Edición visual tipo Tableau.

## Criterios de aceptación

- [ ] “Grafica FC de P001” muestra una línea con ≥5 puntos reales.
- [ ] Hover muestra timestamp y valor.
- [ ] Variable inexistente → mensaje, no gráfico vacío silencioso.

## Riesgos y fallback

- Plotly no carga en el cliente: tabla de los mismos puntos.
- Paciente sin esa variable: se indica la fuente faltante (RF-08).
