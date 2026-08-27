# SPEC-005 — Conexión con modelo preentrenado (proyecto externo)

- Estado: `aceptada`
- Área: 1 Salud
- Relaciona: RF-14, RNF-07, RN-03
- Autor: equipo
- Fecha: 2026-08-26

## Problema

El entrenamiento vive (o vivirá) en **otro repositorio**. Este prototipo no reentrena: consume un servicio HTTP que ya sabe devolver un score de riesgo. Hay que poder demostrarlo aunque ese servicio aún no esté arriba.

## Actor y disparador

- Sistema: al calcular el ranking (enriquecer score).
- Usuario: pregunta “¿qué dice el modelo de P001?”.

## Comportamiento esperado

1. El adaptador `POST {PRETRAINED_MODEL_URL}/predict` con `{ patient_id, features, window }`.
2. Contrato de respuesta: `{ risk_score: 0..1, label, model_version, contributing_features[] }`.
3. Si el servicio no responde en 2 s o no está configurado, se usa el **modelo local de fallback** (mismas features, reglas dinámicas + Isolation Forest ligero) y se etiqueta `source: local_fallback`.
4. El score remoto **no sustituye** el ranking de reglas: se muestra como señal adicional en la tarjeta / chat, separado de la evidencia cruda (RN-06).
5. **Resultado observable:** para un paciente, se ve score + versión del modelo + si vino de remoto o fallback.

## Entradas

- Features alineadas del paciente (últimas 24 h: medias, pendientes, faltantes).
- `PRETRAINED_MODEL_URL` (opcional). Timeout 2 s.

## Salidas

- Bloque `model_opinion` en alerta y en el chat.
- Health: `GET /api/model/status` → `remote` | `fallback`.

## No cubierto

- Entrenar, serializar o versionar el modelo en este repo.
- GPU, MLOps, reentrenamiento con RF-09.
- Autenticación mTLS del servicio externo (hackathon: red local).

## Criterios de aceptación

- [ ] Sin URL remota, `GET /api/model/status` reporta `fallback` y `/predict` igual devuelve un score.
- [ ] Con URL caída, no se rompe el chat ni el ranking; el UI dice “modelo local (el servicio externo no respondió)”.
- [ ] El texto nunca dice “el modelo diagnostica X”.

## Riesgos y fallback

- Contrato distinto en el otro proyecto: el adaptador mapea campos conocidos y si no calza, fallback.
- El otro proyecto tarda: timeout corto, no bloquear el chat.
