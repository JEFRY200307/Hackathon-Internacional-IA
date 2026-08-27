# ADR-0007 — Modelo preentrenado como servicio HTTP externo + fallback local

- Estado: `aceptada`
- Fecha: 2026-08-26
- Decisores: equipo

## Contexto

El entrenamiento no pertenece a este repo (otro proyecto). Este prototipo debe **integrarse**, no reentrenar (fuera de alcance del reto y de las 12 h). El servicio externo puede no existir el día de la demo.

## Decisión

Adaptador HTTP:

- `POST {PRETRAINED_MODEL_URL}/predict`
- Body: `{ patient_id, features, window }`
- Respuesta: `{ risk_score, label, model_version, contributing_features }`
- Timeout 2 s. Si falta URL o falla: motor local (reglas + Isolation Forest simple) con `source: local_fallback`.

El ranking de alertas **no depende** de que el remoto viva; el remoto enriquece, no manda.

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| Copiar `.pkl` al repo | Acopla entrenamiento y app; conflicto con `.gitignore` de modelos. |
| Entrenar aquí | Viola el recorte de GPU/MLOps y el “otro proyecto”. |
| **HTTP + fallback** | Elegida: contrato claro, demo a prueba de red. |

## Consecuencias

- Positivas: el otro equipo puede cambiar el modelo sin tocar el frontend.
- Negativas / deuda: hay que alinear nombres de features cuando exista el servicio real.
- Impacto: RF-14, SPEC-005, RNF-07.

## Reversibilidad

Fácil. Solo cambia la URL y el mapper de features.
