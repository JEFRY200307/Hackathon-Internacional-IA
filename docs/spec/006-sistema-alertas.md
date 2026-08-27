# SPEC-006 — Sistema de alertas por nivel de riesgo

- Estado: `aceptada`
- Área: 1 Salud
- Relaciona: RF-04, RF-05, RF-06, RF-07, RF-09, RF-15, RN-01, RN-02, RN-07
- Autor: equipo
- Fecha: 2026-08-26

## Problema

El profesional necesita una cola priorizada: qué revisar ahora, qué es ruido contextual, y por qué. Un umbral estático por variable no alcanza (OBJ-01).

## Actor y disparador

- Sistema: al arrancar (o al refrescar) calcula el ranking sobre el sample/dataset.
- Usuario: filtra por nivel, abre una alerta, la marca revisada/confirmada/descartada.

## Comportamiento esperado

1. Para cada paciente con ≥2 fuentes (o con hueco explícito), se evalúa patrón temporal + combinación (SPEC-001).
2. Se asigna un nivel: `CRITICO` | `ALTO` | `MEDIO` | `BAJO` | `DESCARTADO`.
3. El listado se ordena CRITICO→BAJO; `DESCARTADO` queda visible en sección secundaria (RN-02), no oculto.
4. Cada alerta trae bundle de evidencia: variables, ventana, fuentes, patrón (`EARLY_SIGNAL` | `PROGRESSIVE` | `TRANSIENT` | `CONTEXTUAL` | `MISSING_SOURCE`).
5. El usuario puede filtrar por nivel y marcar estado HITL: `abierta` | `revisada` | `confirmada` | `descartada`.
6. **Resultado observable:** en la barra lateral hay un ranking; al menos un caso PROGRESSIVE alto y un TRANSIENT/CONTEXTUAL descartado con motivo.

## Entradas

- Series vitales + laboratorio (+ contexto de actividad si existe).
- Opinión del modelo preentrenado (SPEC-005) como feature auxiliar, no como único criterio.

## Salidas

- `GET /api/alerts` lista + conteos por nivel.
- `GET /api/alerts/{id}` detalle con evidencia.
- `POST /api/alerts/{id}/review` cambia estado HITL.

## No cubierto

- Notificaciones push, SMS, integración HIS/FHIR.
- Usar “número de alertas” como métrica de éxito (RN-07).

## Criterios de aceptación

- [ ] Hay ≥1 alerta `ALTO` o `CRITICO` de patrón combinado (no un solo umbral).
- [ ] Hay ≥1 `DESCARTADO` con motivo CONTEXTUAL o TRANSIENT visible.
- [ ] Filtrar por `ALTO` oculta los demás en la lista principal, no borra los descartados del sistema.
- [ ] Marcar `confirmada` persiste en memoria de proceso y se refleja en la UI.

## Riesgos y fallback

- Dataset oficial distinto: el motor de reglas es configurable por nombres de columnas (alias).
- Cero alertas: se muestra vacío explícito + invitación a ver DESCARTADO / calidad de datos.
