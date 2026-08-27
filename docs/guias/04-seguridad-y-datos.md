# Guía — Seguridad y protección de la información

La guía oficial pide explícitamente que la solución "incorpore consideraciones relacionadas con la protección y tratamiento seguro de la información", aun siendo un prototipo. Esto documenta qué se hizo, qué se decidió no hacer y por qué, para que el jurado pueda auditarlo en vez de asumirlo.

## 1. Los datos son sintéticos — y aun así se tratan como sensibles

RISA Data V1.0 es 100 % ficticio (población, instituciones, dispositivos y registros no representan personas reales — lo dice la guía oficial). Aun así, el proyecto trata los IDs de paciente como si fueran PII real (RNF-09 de `definicion.md`): no aparecen en logs de aplicación, no se envían en query strings salvo lo estrictamente necesario para filtrar (`GET /api/alerts?level=`, nunca `?patient_id=` en la URL de una acción sensible), y no se commitea ningún dato "oficial" fuera de lo que el propio reto entrega en `docs/Participantes Salud/`.

## 2. Secretos

- `backend/.env` está en `.gitignore`; solo `.env.example` (sin valores reales) se versiona.
- La única credencial del sistema es `OPENAI_API_KEY`, opcional — sin ella, el backend cae a `MockLLM` sin perder funcionalidad (`ADR-0004`). Esto significa que el prototipo completo se puede demostrar y auditar **sin que exista ningún secreto en el entorno**.
- `frontend/.env.example` solo expone `VITE_API_URL` (una URL local, no un secreto).

## 3. Superficie de red

- CORS restringido por configuración (`Settings.cors_origins`) a los orígenes de desarrollo declarados — nunca `allow_origins=["*"]` en el middleware de FastAPI (`app/main.py`).
- El adaptador al modelo preentrenado externo (`app/adapters/pretrained.py`) usa un timeout corto (2 s) y captura cualquier excepción de red para caer al fallback local — un servicio externo caído o lento no puede convertirse en una vía de denegación de servicio del backend.
- No hay autenticación de usuario en este prototipo (no la pide el alcance de 12 h y no hay múltiples roles reales que distinguir todavía). Es una limitación conocida, no un descuido: se declara así en el README en vez de aparentar una seguridad que no existe.

## 4. Separación de responsabilidades como control de exposición

`pipeline/` es el único componente con acceso a los CSV crudos de RISA; el backend nunca abre esos archivos directamente (`ADR-0008`). Esto significa que la superficie que "toca disco" está en un solo lugar auditable, y que el backend solo puede servir lo que el pipeline decidió exponer en `PipelineResult` — no puede, por accidente, filtrar una columna cruda que no pasó por limpieza/normalización.

## 5. IA generativa: qué puede y qué no puede hacer

- El LLM (`gpt-4o` o `MockLLM`) nunca escribe directamente sobre el dataset ni sobre `results/` — solo lee, a través de `tools` explícitas (`llm/tools.py`). No hay una tool de escritura expuesta al modelo.
- Toda afirmación del chat sobre un paciente debe originarse en una tool (dataset, alertas, RAG, modelo) — es una regla en el propio `SYSTEM_PROMPT`, reforzada por la separación evidencia/explicación (RN-06, ver [02-arquitectura-y-patrones.md](02-arquitectura-y-patrones.md) punto 7).
- Declaración de tecnología generativa (exigida por la guía oficial): `gpt-4o` de OpenAI vía API, uso opcional y con fallback determinista; sin fine-tuning; sin envío de datos de RISA a ningún servicio de entrenamiento (las llamadas a la API de OpenAI son de inferencia, no de entrenamiento).

## 6. Qué falta para producción (deuda declarada, no oculta)

Esta lista es intencional — nombrarla es parte de responder con honestidad a "impacto y escalabilidad" en el pitch, no un pendiente vergonzoso:

- Autenticación/autorización por rol (profesional de salud vs. curador de datos vs. administrador de institución).
- Auditoría persistente de accesos (hoy `review_status` se guarda en memoria del proceso, se pierde al reiniciar).
- Cifrado en tránsito (HTTPS) — depende del entorno de despliegue, no del código de la aplicación.
- Gestión de secretos vía un vault en vez de `.env` — razonable recién quando hay múltiples entornos reales que gestionar.
