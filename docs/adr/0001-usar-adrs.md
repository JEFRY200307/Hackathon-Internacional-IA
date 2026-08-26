# ADR-0001 — Usar Architecture Decision Records

- Estado: `aceptada`
- Fecha: 2026-08-26
- Decisores: equipo

## Contexto

El reto específico se revela al inicio de la Hackathon y el tiempo de desarrollo es ~12 h. Hace falta un formato corto para fijar stack, recortes de alcance y trade-offs sin reabrir debates.

## Decisión

Toda decisión de arquitectura, stack o recorte de alcance se registra como ADR en `docs/adr/`, usando el arquetipo `docs/archetypes/adr.md`.

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| Solo chat / memoria del equipo | Se pierde el hilo y no hay rastro para el jurado ni para el propio equipo |
| Documento único de arquitectura largo | Demasiado pesado para 12 h |
| ADRs cortos | Elegida: una decisión, una página, reversible |

## Consecuencias

- Positivas: decisiones explícitas, recortes defendibles, menos ida y vuelta.
- Negativas / deuda: hay que escribir 5–10 minutos por decisión.
- Impacto en RF / RNF / RN: ninguno directo; sostiene trazabilidad.

## Reversibilidad

Fácil. Dejar de escribir ADRs no rompe el prototipo.
