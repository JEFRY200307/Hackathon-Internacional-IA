# Documentación

Fuente de verdad del prototipo de la Hackathon. Aquí viven la definición del proyecto, las especificaciones, las decisiones de arquitectura y los arquetipos (plantillas) para crear documentos nuevos.

## Cómo usar esta carpeta

1. Empezar siempre por [`definicion.md`](definicion.md): visión, alcance, RF, RNF, RN y criterios de éxito.
2. Para entender la idea completa (narrativa, sin tablas de requisitos), diagramas, stack y árbol de carpetas: [`arquitectura.md`](arquitectura.md).
3. Cada capacidad o flujo visible se documenta en [`spec/`](spec/) a partir del arquetipo.
4. Cada decisión técnica relevante se registra en [`adr/`](adr/) a partir del arquetipo.
5. No duplicar contenido: la definición dice *qué* y *por qué*; la arquitectura cuenta *la idea y con qué se construye*; las specs dicen *cómo se comporta*; los ADR dicen *qué se eligió y qué se descartó*.

## Mapa

| Ruta | Para qué |
| --- | --- |
| [`definicion.md`](definicion.md) | Documento vivo del proyecto (objetivos, RF, RNF, RN, restricciones) |
| [`arquitectura.md`](arquitectura.md) | La idea explicada en prosa, diagramas de arquitectura (visión completa y MVP), stack propuesto y árbol de carpetas |
| [`spec/`](spec/) | SPEC-001 … SPEC-009 (flujo, chat, RISA UI, gráficos, modelo, alertas, RAG, pipeline CRISP-DM, evaluación) |
| [`adr/`](adr/) | ADR-0001 … ADR-0009 |
| [`guias/`](guias/) | Estándares de API, arquitectura y patrones, frontend, seguridad — el *cómo* se construye |
| [`archetypes/`](archetypes/) | Plantillas reutilizables |
| [`Participantes Salud/`](Participantes%20Salud/) | Material oficial de referencia del reto (guías, kit de entrega) — el dataset RISA Data V1.0 vive en [`pipeline/data/raw/`](../pipeline/data/raw/) |
| [`Negocio.md`](Negocio.md), [`diccionario_datos.md`](diccionario_datos.md), [`data_inventory_report.md`](data_inventory_report.md) | Comprensión del negocio y de los datos (CRISP-DM fases 1-2), mapeadas a código en [`pipeline/comprension_negocio.md`](../pipeline/comprension_negocio.md) |

## Convención de IDs

- Requisitos funcionales: `RF-XX`
- Requisitos no funcionales: `RNF-XX`
- Reglas de negocio: `RN-XX`
- Specs: `SPEC-XXX` (archivo `XXX-slug.md`)
- ADR: `ADR-XXXX` (archivo `XXXX-slug.md`)

Los IDs no se reutilizan. Si un ítem se descarta, se marca como `descartado` y se deja el ID ocupado.
