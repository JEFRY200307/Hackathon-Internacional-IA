# Arquetipos

Plantillas para crear documentos del mismo tipo sin reinventar la estructura. Copiar el archivo, numerarlo y rellenar. No editar el arquetipo “en caliente” para un caso concreto.

| Arquetipo | Uso | Destino al instanciar |
| --- | --- | --- |
| [`spec.md`](spec.md) | Comportamiento de un flujo o capacidad | `docs/spec/XXX-slug.md` |
| [`adr.md`](adr.md) | Decisión de arquitectura o stack | `docs/adr/XXXX-slug.md` |
| [`rfc.md`](rfc.md) | Propuesta a discutir antes de decidir | se discute; si se acepta, nace spec y/o ADR |
| [`glosario.md`](glosario.md) | Término de dominio | sección Glosario en `definicion.md` o archivo dedicado |
| [`riesgo.md`](riesgo.md) | Riesgo del prototipo | sección Riesgos en `definicion.md` |
