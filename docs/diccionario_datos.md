# Diccionario de Datos Completo y Exhaustivo - RISA Data V1.0
Este archivo describe de manera detallada todas las tablas principales de datos 
asistenciales, clínicos y fisiológicos sintéticos pertenecientes a la Red de Salud Andina (RISA).

##  Archivo: `01_master/devices.csv`
**Descripción:** Catálogo de dispositivos médicos y wearables activos y asignados en la red RISA.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `device_id` | **PK** | *string* | Identificador único del dispositivo médico o wearable. |
| `device_type` | - | *category* | Tipo de sensor (wearable, clinical_monitor, etc.). |
| `manufacturer_class` | - | *string* | Clasificación de calidad del fabricante. |
| `model_family` | - | *string* | Familia tecnológica o modelo del sensor. |
| `measurement_domain` | - | *category* | Dominio de las variables que mide (VITAL, WEARABLE, etc.). |
| `sampling_profile` | - | *category* | Frecuencia típica de captura de datos. |
| `reliability_class` | - | *category* | Nivel de confiabilidad técnica asignado al dispositivo. |
| `facility_id` | **FK** | *string* | Referencia a la sede donde reside el sensor (hacia healthcare_facilities.csv). |
| `patient_assignment_type` | - | *category* | Tipo de asignación (fixed, temporary). |
| `active` | - | *boolean* | Indica si el dispositivo está encendido o transmitiendo (True/False). |
| `assigned_patient_id` | **FK** | *string* | Identificador del paciente que tiene asignado el sensor (FK opcional). |

--------------------------------------------------

## Archivo: `01_master/encounters.csv`
**Descripción:** Registra los episodios de monitoreo clínico u hospitalizaciones asistenciales del paciente.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `encounter_id` | **PK** | *string* | Identificador único del encuentro o episodio clínico. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `facility_id` | **FK** | *string* | Referencia a la sede médica (hacia healthcare_facilities.csv). |
| `encounter_type` | - | *category* | Tipo de encuentro clínico (inpatient, outpatient, etc.). |
| `start_datetime` | - | *datetime* | Fecha y hora de inicio de la atención médica. |
| `end_datetime` | - | *datetime* | Fecha y hora de finalización de la atención médica. |
| `care_setting` | - | *category* | Entorno o modalidad donde se presta la atención. |
| `reason_category` | - | *category* | Motivo o diagnóstico principal del encuentro. |
| `source_system` | - | *category* | Sistema electrónico de salud (EHR) de origen. |
| `status` | - | *category* | Estado actual del episodio (completed, active, etc.). |

--------------------------------------------------

## Archivo: `01_master/healthcare_facilities.csv`
**Descripción:** Detalla los establecimientos médicos pertenecientes a la Red Integrada de Salud Andina (RISA).

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `facility_id` | **PK** | *string* | Identificador único de la sede médica de RISA. |
| `facility_name` | - | *string* | Nombre comercial o clínico de la sede. |
| `facility_type` | - | *category* | Tipo de sede (Hospital, Clínica Metropolitana, Centro Primario, etc.). |
| `region_type` | - | *category* | Tipo de ubicación geográfica de la sede (urban, rural). |
| `digital_maturity` | - | *category* | Clasificación de madurez digital interna (High, Medium, Low). |
| `connectivity_profile` | - | *category* | Perfil o estabilidad de red de la instalación. |
| `monitoring_capability` | - | *category* | Capacidad tecnológica instalada para telemonitoreo continuo. |
| `laboratory_capability` | - | *category* | Capacidad analítica de laboratorios clínicos integrados. |

--------------------------------------------------

## Archivo: `01_master/patients.csv`
**Descripción:** Contiene el perfil demográfico básico de los pacientes sintéticos de la red RISA.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `patient_id` | **PK** | *string* | Identificador único y canónico del paciente sintético. |
| `sex_at_birth` | - | *category* | Sexo biológico registrado al nacer. |
| `age_years` | - | *int* | Edad exacta del paciente en años. |
| `age_group` | - | *category* | Grupo etario del paciente (adult, elderly, etc.). |
| `region_type` | - | *category* | Tipo de región geográfica del paciente (urban, rural). |
| `care_program` | - | *category* | Programa asistencial de RISA en el que está enrolado el paciente. |
| `baseline_risk_profile` | - | *category* | Perfil de riesgo de base calculado por la clínica. |
| `enrollment_date` | - | *date* | Fecha de registro o enrolamiento del paciente en la red. |
| `active` | - | *boolean* | Indica si el paciente está activo en los registros (True/False). |

--------------------------------------------------

## Archivo: `02_clinical/conditions.csv`
**Descripción:** Registra las patologías crónicas e historial de enfermedades activas de los pacientes.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `condition_id` | **PK** | *string* | Identificador único del registro de la enfermedad. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `condition_category` | - | *category* | Categoría clínica (CARDIOVASCULAR_HISTORY, RENAL_HISTORY, etc.). |
| `onset_date` | - | *date* | Fecha estimada del primer diagnóstico clínico. |
| `status` | - | *category* | Estado de la condición (ACTIVE, RECORDED, etc.). |
| `severity_context` | - | *category* | Severidad de la patología. |
| `source_system` | - | *category* | Sistema clínico emisor del diagnóstico (EHR_CORE). |
| `recorded_datetime` | - | *datetime* | Fecha y hora exacta en la que se grabó en el EHR. |

--------------------------------------------------

## Archivo: `02_clinical/laboratory_results.csv`
**Descripción:** Resultados de pruebas analíticas de laboratorio. Contiene latencias de publicación.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `lab_result_id` | **PK** | *string* | Identificador único del resultado analítico de laboratorio. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `encounter_id` | **FK** | *string* | Referencia al encuentro clínico (hacia encounters.csv). |
| `test_code` | - | *category* | Código analítico del marcador (LAB_A, LAB_B, LAB_C, LAB_D). |
| `test_name` | - | *string* | Nombre de la prueba de laboratorio clínico. |
| `result_value` | - | *float* | Valor de concentración o resultado numérico obtenido. |
| `unit` | - | *string* | Unidad de medida del resultado analítico (uA, uB, etc.). |
| `reference_low` | - | *float* | Límite normal inferior admisible del biomarcador. |
| `reference_high` | - | *float* | Límite normal superior admisible del biomarcador. |
| `sample_datetime` | - | *datetime* | Fecha y hora de extracción física de la muestra biológica. |
| `result_datetime` | - | *datetime* | Fecha y hora de publicación digital del resultado (tiempo de disponibilidad). |
| `facility_id` | **FK** | *string* | Referencia a la sede donde se procesó (hacia healthcare_facilities.csv). |
| `source_system` | - | *category* | Laboratorio que reportó la prueba (LAB_SYS_A, LAB_SYS_B). |
| `quality_flag` | - | *category* | Metadato técnico sobre la calidad del ensayo analítico. |

--------------------------------------------------

## Archivo: `02_clinical/medication_administrations.csv`
**Descripción:** Registro de dosis efectivas administradas a los pacientes.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `administration_id` | **PK** | *string* | Identificador de la administración de la dosis. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `encounter_id` | **FK** | *string* | Referencia al encuentro clínico (hacia encounters.csv). |
| `medication_id` | **FK** | *string* | Referencia al medicamento catálogo (hacia medications.csv). |
| `start_datetime` | - | *datetime* | Fecha y hora de inicio del suministro del fármaco. |
| `end_datetime` | - | *datetime* | Fecha y hora de término de la infusión o toma. |
| `dose_value` | - | *float* | Magnitud o volumen de la dosis suministrada. |
| `dose_unit` | - | *string* | Unidad de dosificación física. |
| `administration_status` | - | *category* | Estado del proceso de entrega (completed, etc.). |
| `source_system` | - | *category* | Módulo clínico del EHR emisor del registro (EHR_MED). |

--------------------------------------------------

## Archivo: `02_clinical/medications.csv`
**Descripción:** Catálogo general de fármacos y compuestos prescritos en la red de RISA.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `medication_id` | **PK** | *string* | Identificador único de la molécula o medicamento en catálogo. |
| `medication_class` | - | *string* | Clase terapéutica o clasificación ATC. |
| `generic_category` | - | *string* | Familia genérica del principio activo. |
| `administration_route` | - | *category* | Vía estándar de entrada al organismo (ORAL, IV, etc.). |

--------------------------------------------------

## Archivo: `03_monitoring/device_observations.csv`
**Descripción:** Registros de flujo continuo generados por equipos y monitores de cama en unidades asistenciales.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `device_observation_id` | **PK** | *string* | Identificador único del registro de telemetría continua de cama. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `encounter_id` | **FK** | *string* | Referencia al encuentro médico de soporte (hacia encounters.csv). |
| `device_id` | **FK** | *string* | Dispositivo clínico conectado (hacia devices.csv). |
| `timestamp` | - | *datetime* | Fecha y hora del registro del flujo continuo. |
| `variable_code` | - | *category* | Variable capturada por telemetría clínica o de soporte. |
| `value` | - | *float* | Magnitud de la observación fisiológica. |
| `unit` | - | *string* | Unidad de medida asociada. |
| `signal_quality` | - | *float* | Relación de calidad o estabilidad de la señal continua (0 a 1). |
| `source_system` | - | *category* | Gateway que emite el flujo (MONITOR_GATEWAY). |

--------------------------------------------------

## Archivo: `03_monitoring/vital_signs.csv`
**Descripción:** Frecuencias y mediciones intrahospitalarias de signos vitales estándar.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `observation_id` | **PK** | *string* | Identificador único del registro de signos vitales clínicos. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `encounter_id` | **FK** | *string* | Referencia al encuentro de hospitalización (hacia encounters.csv). |
| `timestamp` | - | *datetime* | Fecha y hora fisiológica en la que se tomó la medición. |
| `variable_code` | - | *category* | Código del signo vital (HR, RR, SpO2, TEMP, SBP, DBP). |
| `value` | - | *float* | Valor cuantitativo del signo vital observado. |
| `unit` | - | *string* | Unidad de medida del signo (bpm, rpm, %, degC, mmHg). |
| `device_id` | **FK** | *string* | Dispositivo clínico asociado a la toma (hacia devices.csv). |
| `source_system` | - | *category* | Sistema/gateway clínico receptor de la telemetría. |
| `quality_flag` | - | *category* | Bandera técnica que denota la confianza física en el dato. |

--------------------------------------------------

## Archivo: `03_monitoring/wearable_observations.csv`
**Descripción:** Observaciones continuas transmitidas por wearables o dispositivos personales del paciente.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `wearable_observation_id` | **PK** | *string* | Identificador único de la observación remota de wearables. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `device_id` | **FK** | *string* | Referencia al wearable emisor (hacia devices.csv). |
| `timestamp` | - | *datetime* | Fecha y hora del reloj del dispositivo al capturar el dato (tiempo de medición). |
| `variable_code` | - | *category* | Código de variable remota (WEARABLE_HR, STEPS). |
| `value` | - | *float* | Valor registrado por el wearable. |
| `unit` | - | *string* | Unidad del dato obtenido (bpm, count). |
| `measurement_quality` | - | *category* | Índice de confianza de señal estimado por el dispositivo móvil. |
| `sync_datetime` | - | *datetime* | Instante operacional en que los datos se sincronizan en la nube (tiempo de disponibilidad). |

--------------------------------------------------

## Archivo: `04_context/connectivity_events.csv`
**Descripción:** Log técnico de fallas de red, desconexiones físicas o retrasos en la subida de datos IoT.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `event_id` | **PK** | *string* | Identificador único del fallo o desconexión temporal de red. |
| `device_id` | **FK** | *string* | Dispositivo con pérdida de conexión (hacia devices.csv). |
| `patient_id` | **FK** | *string* | Paciente afectado indirectamente (hacia patients.csv). |
| `start_datetime` | - | *datetime* | Inicio del evento de desconexión física o caída. |
| `end_datetime` | - | *datetime* | Término del evento y restablecimiento del canal. |
| `connectivity_status` | - | *category* | Estado de red observado (DISCONNECTED, DELAYED_SYNC, INTERMITTENT). |
| `delayed_records` | - | *int* | Conteo de registros acumulados en buffer durante la caída. |
| `packet_loss_estimate` | - | *float* | Tasa estimada de pérdida de paquetes en el canal (0 a 1). |

--------------------------------------------------

## Archivo: `04_context/patient_context.csv`
**Descripción:** Estados de sueño, vigilia o niveles de actividad física que sirven para contextualizar las constantes vitales.

| Campo | Rol Llave | Tipo de Dato | Descripción / Significado Clínico |
|---|---|---|---|
| `context_id` | **PK** | *string* | Identificador único del intervalo de contexto del paciente. |
| `patient_id` | **FK** | *string* | Referencia al paciente (hacia patients.csv). |
| `start_datetime` | - | *datetime* | Fecha y hora de inicio del estado de contexto. |
| `end_datetime` | - | *datetime* | Fecha y hora de término del estado de contexto. |
| `context_type` | - | *category* | Variable de contexto (ACTIVITY_LEVEL, SLEEP_STATE, etc.). |
| `context_value` | - | *category* | Valor del estado en el rango (sleeping, resting, active). |
| `source` | - | *string* | Componente o algoritmo que estimó este estado contextual. |
| `confidence` | - | *float* | Índice de confianza en la estimación del contexto (0 a 1). |

--------------------------------------------------
