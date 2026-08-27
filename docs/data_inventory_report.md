# Reporte de Inventario de Datos - RISA Data V1.0

Este reporte resume la estructura de archivos, dimensiones, memoria y estadísticas de calidad del dataset.

## Resumen General de Archivos

| Archivo | Número de Registros | Número de Columnas | Memoria | Filas Duplicadas |
|---|---|---|---|---|
| `01_master\devices.csv` | 2,000 | 11 | 1.12 MB | 0 |
| `01_master\encounters.csv` | 1,000 | 10 | 601.94 KB | 0 |
| `01_master\healthcare_facilities.csv` | 7 | 8 | 3.29 KB | 0 |
| `01_master\patients.csv` | 1,000 | 9 | 400.50 KB | 0 |
| `02_clinical\conditions.csv` | 1,484 | 8 | 703.96 KB | 0 |
| `02_clinical\laboratory_results.csv` | 4,593 | 14 | 3.06 MB | 0 |
| `02_clinical\medication_administrations.csv` | 856 | 10 | 472.65 KB | 0 |
| `02_clinical\medications.csv` | 5 | 4 | 1.30 KB | 0 |
| `03_monitoring\device_observations.csv` | 13,329 | 10 | 6.46 MB | 0 |
| `03_monitoring\vital_signs.csv` | 1,622,969 | 10 | 822.60 MB | 0 |
| `03_monitoring\wearable_observations.csv` | 895,551 | 9 | 454.43 MB | 0 |
| `04_context\connectivity_events.csv` | 434 | 8 | 169.20 KB | 0 |
| `04_context\patient_context.csv` | 8,830 | 8 | 3.72 MB | 0 |
| `05_metadata\data_dictionary.csv` | 11 | 5 | 3.48 KB | 0 |
| `05_metadata\source_catalog.csv` | 7 | 7 | 3.04 KB | 0 |
| `05_metadata\units_catalog.csv` | 13 | 6 | 3.17 KB | 0 |
| `05_metadata\variable_catalog.csv` | 15 | 8 | 5.53 KB | 0 |

==================================================

## Detalle Específico por Archivo

### Archivo: `01_master\devices.csv`
* **Registros totales:** 2,000
* **Duplicados totales:** 0
* **Uso de memoria:** 1.12 MB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `device_id` | *str* | 0 (0.0%) | 2,000 | - | - |
| `device_type` | *str* | 0 (0.0%) | 3 | - | - |
| `manufacturer_class` | *str* | 0 (0.0%) | 1 | - | - |
| `model_family` | *str* | 0 (0.0%) | 9 | - | - |
| `measurement_domain` | *str* | 0 (0.0%) | 2 | - | - |
| `sampling_profile` | *str* | 0 (0.0%) | 2 | - | - |
| `reliability_class` | *str* | 0 (0.0%) | 3 | - | - |
| `facility_id` | *str* | 0 (0.0%) | 3 | - | - |
| `patient_assignment_type` | *str* | 0 (0.0%) | 1 | - | - |
| `active` | *bool* | 0 (0.0%) | 1 | - | - |
| `assigned_patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |

--------------------------------------------------

### Archivo: `01_master\encounters.csv`
* **Registros totales:** 1,000
* **Duplicados totales:** 0
* **Uso de memoria:** 601.94 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `encounter_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `facility_id` | *str* | 0 (0.0%) | 3 | - | - |
| `encounter_type` | *str* | 0 (0.0%) | 3 | - | - |
| `start_datetime` | *str* | 0 (0.0%) | 489 | 2026-07-01 00:00:00 | 2026-07-28 18:15:00 |
| `end_datetime` | *str* | 0 (0.0%) | 462 | 2026-07-04 00:00:00 | 2026-07-31 08:00:00 |
| `care_setting` | *str* | 0 (0.0%) | 2 | - | - |
| `reason_category` | *str* | 0 (0.0%) | 1 | - | - |
| `source_system` | *str* | 0 (0.0%) | 1 | - | - |
| `status` | *str* | 0 (0.0%) | 1 | - | - |

--------------------------------------------------

### Archivo: `01_master\healthcare_facilities.csv`
* **Registros totales:** 7
* **Duplicados totales:** 0
* **Uso de memoria:** 3.29 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `facility_id` | *str* | 0 (0.0%) | 7 | - | - |
| `facility_name` | *str* | 0 (0.0%) | 7 | - | - |
| `facility_type` | *str* | 0 (0.0%) | 6 | - | - |
| `region_type` | *str* | 0 (0.0%) | 4 | - | - |
| `digital_maturity` | *str* | 0 (0.0%) | 5 | - | - |
| `connectivity_profile` | *str* | 0 (0.0%) | 3 | - | - |
| `monitoring_capability` | *str* | 0 (0.0%) | 5 | - | - |
| `laboratory_capability` | *str* | 0 (0.0%) | 4 | - | - |

--------------------------------------------------

### Archivo: `01_master\patients.csv`
* **Registros totales:** 1,000
* **Duplicados totales:** 0
* **Uso de memoria:** 400.50 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `sex_at_birth` | *str* | 0 (0.0%) | 2 | - | - |
| `age_years` | *int64* | 0 (0.0%) | 72 | - | - |
| `age_group` | *str* | 0 (0.0%) | 4 | - | - |
| `region_type` | *str* | 0 (0.0%) | 3 | - | - |
| `care_program` | *str* | 0 (0.0%) | 4 | - | - |
| `baseline_risk_profile` | *str* | 0 (0.0%) | 4 | - | - |
| `enrollment_date` | *str* | 0 (0.0%) | 170 | 2026-01-02 00:00:00 | 2026-06-21 00:00:00 |
| `active` | *bool* | 0 (0.0%) | 1 | - | - |

--------------------------------------------------

### Archivo: `02_clinical\conditions.csv`
* **Registros totales:** 1,484
* **Duplicados totales:** 0
* **Uso de memoria:** 703.96 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `condition_id` | *str* | 0 (0.0%) | 1,484 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `condition_category` | *str* | 0 (0.0%) | 5 | - | - |
| `onset_date` | *str* | 0 (0.0%) | 1,055 | 2020-06-23 00:00:00 | 2026-03-01 00:00:00 |
| `status` | *str* | 0 (0.0%) | 2 | - | - |
| `severity_context` | *str* | 0 (0.0%) | 1 | - | - |
| `source_system` | *str* | 0 (0.0%) | 1 | - | - |
| `recorded_datetime` | *str* | 0 (0.0%) | 196 | 2025-12-13 00:00:00 | 2026-06-26 00:00:00 |

--------------------------------------------------

### Archivo: `02_clinical\laboratory_results.csv`
* **Registros totales:** 4,593
* **Duplicados totales:** 0
* **Uso de memoria:** 3.06 MB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `lab_result_id` | *str* | 0 (0.0%) | 4,593 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `encounter_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `test_code` | *str* | 0 (0.0%) | 4 | - | - |
| `test_name` | *str* | 0 (0.0%) | 4 | - | - |
| `result_value` | *float64* | 0 (0.0%) | 2,919 | - | - |
| `unit` | *str* | 0 (0.0%) | 4 | - | - |
| `reference_low` | *float64* | 0 (0.0%) | 3 | - | - |
| `reference_high` | *float64* | 0 (0.0%) | 4 | - | - |
| `sample_datetime` | *str* | 0 (0.0%) | 1,870 | 2026-07-01 04:55:43 | 2026-07-31 02:07:55 |
| `result_datetime` | *str* | 0 (0.0%) | 4,579 | 2026-07-01 08:21:43 | 2026-07-31 04:36:55 |
| `facility_id` | *str* | 0 (0.0%) | 1 | - | - |
| `source_system` | *str* | 0 (0.0%) | 2 | - | - |
| `quality_flag` | *str* | 0 (0.0%) | 1 | - | - |

--------------------------------------------------

### Archivo: `02_clinical\medication_administrations.csv`
* **Registros totales:** 856
* **Duplicados totales:** 0
* **Uso de memoria:** 472.65 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `administration_id` | *str* | 0 (0.0%) | 856 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 618 | - | - |
| `encounter_id` | *str* | 0 (0.0%) | 618 | - | - |
| `medication_id` | *str* | 0 (0.0%) | 5 | - | - |
| `start_datetime` | *str* | 0 (0.0%) | 855 | 2026-07-01 16:50:56 | 2026-07-30 20:38:38 |
| `end_datetime` | *str* | 0 (0.0%) | 855 | 2026-07-01 20:50:56 | 2026-07-31 04:38:38 |
| `dose_value` | *int64* | 0 (0.0%) | 4 | - | - |
| `dose_unit` | *str* | 0 (0.0%) | 1 | - | - |
| `administration_status` | *str* | 0 (0.0%) | 1 | - | - |
| `source_system` | *str* | 0 (0.0%) | 1 | - | - |

--------------------------------------------------

### Archivo: `02_clinical\medications.csv`
* **Registros totales:** 5
* **Duplicados totales:** 0
* **Uso de memoria:** 1.30 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `medication_id` | *str* | 0 (0.0%) | 5 | - | - |
| `medication_class` | *str* | 0 (0.0%) | 5 | - | - |
| `generic_category` | *str* | 0 (0.0%) | 5 | - | - |
| `administration_route` | *str* | 0 (0.0%) | 3 | - | - |

--------------------------------------------------

### Archivo: `03_monitoring\device_observations.csv`
* **Registros totales:** 13,329
* **Duplicados totales:** 0
* **Uso de memoria:** 6.46 MB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `device_observation_id` | *str* | 0 (0.0%) | 13,329 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `encounter_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `device_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `timestamp` | *str* | 0 (0.0%) | 2,455 | 2026-07-01 00:00:00 | 2026-07-31 08:00:00 |
| `variable_code` | *str* | 0 (0.0%) | 1 | - | - |
| `value` | *float64* | 0 (0.0%) | 262 | - | - |
| `unit` | *str* | 0 (0.0%) | 1 | - | - |
| `signal_quality` | *float64* | 0 (0.0%) | 262 | - | - |
| `source_system` | *str* | 0 (0.0%) | 1 | - | - |

--------------------------------------------------

### Archivo: `03_monitoring\vital_signs.csv`
* **Registros totales:** 1,622,969
* **Duplicados totales:** 0
* **Uso de memoria:** 822.60 MB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `observation_id` | *str* | 0 (0.0%) | 1,622,969 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `encounter_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `timestamp` | *str* | 0 (0.0%) | 8,497 | 2026-07-01 00:00:00 | 2026-07-31 08:00:00 |
| `variable_code` | *str* | 0 (0.0%) | 6 | - | - |
| `value` | *float64* | 0 (0.0%) | 101,380 | - | - |
| `unit` | *str* | 0 (0.0%) | 6 | - | - |
| `device_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `source_system` | *str* | 0 (0.0%) | 2 | - | - |
| `quality_flag` | *str* | 0 (0.0%) | 5 | - | - |

--------------------------------------------------

### Archivo: `03_monitoring\wearable_observations.csv`
* **Registros totales:** 895,551
* **Duplicados totales:** 0
* **Uso de memoria:** 454.43 MB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `wearable_observation_id` | *str* | 0 (0.0%) | 895,551 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `device_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `timestamp` | *str* | 0 (0.0%) | 2,866 | 2026-07-01 00:00:00 | 2026-07-31 08:00:00 |
| `variable_code` | *str* | 0 (0.0%) | 3 | - | - |
| `value` | *str* | 0 (0.0%) | 46,160 | - | - |
| `unit` | *str* | 0 (0.0%) | 3 | - | - |
| `measurement_quality` | *str* | 0 (0.0%) | 1 | - | - |
| `sync_datetime` | *str* | 0 (0.0%) | 35,737 | 2026-07-01 00:00:00 | 2026-07-31 08:07:00 |

--------------------------------------------------

### Archivo: `04_context\connectivity_events.csv`
* **Registros totales:** 434
* **Duplicados totales:** 0
* **Uso de memoria:** 169.20 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `event_id` | *str* | 0 (0.0%) | 434 | - | - |
| `device_id` | *str* | 0 (0.0%) | 406 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 406 | - | - |
| `start_datetime` | *str* | 0 (0.0%) | 428 | 2026-07-01 10:54:42 | 2026-07-30 21:21:18 |
| `end_datetime` | *str* | 0 (0.0%) | 428 | 2026-07-01 13:54:42 | 2026-07-30 22:21:18 |
| `connectivity_status` | *str* | 0 (0.0%) | 3 | - | - |
| `delayed_records` | *int64* | 0 (0.0%) | 33 | - | - |
| `packet_loss_estimate` | *float64* | 0 (0.0%) | 31 | - | - |

--------------------------------------------------

### Archivo: `04_context\patient_context.csv`
* **Registros totales:** 8,830
* **Duplicados totales:** 0
* **Uso de memoria:** 3.72 MB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `context_id` | *str* | 0 (0.0%) | 8,830 | - | - |
| `patient_id` | *str* | 0 (0.0%) | 1,000 | - | - |
| `start_datetime` | *str* | 0 (0.0%) | 1,392 | 2026-07-01 05:00:00 | 2026-07-31 05:00:00 |
| `end_datetime` | *str* | 0 (0.0%) | 1,904 | 2026-07-01 05:30:00 | 2026-07-31 06:00:00 |
| `context_type` | *str* | 0 (0.0%) | 3 | - | - |
| `context_value` | *str* | 0 (0.0%) | 5 | - | - |
| `source` | *str* | 0 (0.0%) | 1 | - | - |
| `confidence` | *float64* | 0 (0.0%) | 3 | - | - |

--------------------------------------------------

### Archivo: `05_metadata\data_dictionary.csv`
* **Registros totales:** 11
* **Duplicados totales:** 0
* **Uso de memoria:** 3.48 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `file` | *str* | 0 (0.0%) | 7 | - | - |
| `field` | *str* | 0 (0.0%) | 9 | - | - |
| `type` | *str* | 0 (0.0%) | 3 | - | - |
| `key_role` | *str* | 8 (72.7%) | 2 | - | - |
| `description` | *str* | 0 (0.0%) | 11 | - | - |

--------------------------------------------------

### Archivo: `05_metadata\source_catalog.csv`
* **Registros totales:** 7
* **Duplicados totales:** 0
* **Uso de memoria:** 3.04 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `source_system` | *str* | 0 (0.0%) | 7 | - | - |
| `source_name` | *str* | 0 (0.0%) | 7 | - | - |
| `source_type` | *str* | 0 (0.0%) | 4 | - | - |
| `update_frequency` | *str* | 0 (0.0%) | 4 | - | - |
| `interoperability_level` | *str* | 0 (0.0%) | 2 | - | - |
| `typical_latency` | *str* | 0 (0.0%) | 6 | - | - |
| `description` | *str* | 0 (0.0%) | 7 | - | - |

--------------------------------------------------

### Archivo: `05_metadata\units_catalog.csv`
* **Registros totales:** 13
* **Duplicados totales:** 0
* **Uso de memoria:** 3.17 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `unit_code` | *str* | 0 (0.0%) | 13 | - | - |
| `unit_name` | *str* | 0 (0.0%) | 13 | - | - |
| `dimension` | *str* | 0 (0.0%) | 7 | - | - |
| `canonical_unit` | *str* | 0 (0.0%) | 12 | - | - |
| `conversion_factor` | *float64* | 0 (0.0%) | 2 | - | - |
| `conversion_offset` | *float64* | 0 (0.0%) | 2 | - | - |

--------------------------------------------------

### Archivo: `05_metadata\variable_catalog.csv`
* **Registros totales:** 15
* **Duplicados totales:** 0
* **Uso de memoria:** 5.53 KB

| Columna | Tipo de Dato | Valores Nulos | Cardinalidad | Fecha Mínima | Fecha Máxima |
|---|---|---|---|---|---|
| `variable_code` | *str* | 0 (0.0%) | 15 | - | - |
| `variable_name` | *str* | 0 (0.0%) | 15 | - | - |
| `domain` | *str* | 0 (0.0%) | 5 | - | - |
| `canonical_unit` | *str* | 0 (0.0%) | 12 | - | - |
| `plausibility_min` | *float64* | 2 (13.3%) | 6 | - | - |
| `plausibility_max` | *float64* | 2 (13.3%) | 11 | - | - |
| `nominal_sampling` | *str* | 0 (0.0%) | 8 | - | - |
| `analysis_role` | *str* | 0 (0.0%) | 5 | - | - |

--------------------------------------------------
