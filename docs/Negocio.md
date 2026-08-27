# 1. Comprensión del negocio

## 1.1. Contexto de RISA

### 1.1.1. Contexto institucional

HealthSignal LATAM se desarrolla sobre **RISA (Red Integrada de Salud Andina)**, un escenario sanitario ficticio diseñado para representar los desafíos de integración de información que pueden presentarse en redes de salud latinoamericanas. RISA integra diferentes niveles y modalidades de atención, incluyendo hospitales, clínicas, atención primaria, monitoreo domiciliario, laboratorios y plataformas de telemonitoreo. Los pacientes, instituciones, dispositivos y registros utilizados en el escenario son completamente sintéticos y no representan personas u organizaciones reales. 

El escenario no parte de un ecosistema tecnológico homogéneo. Las diferentes unidades de la red presentan distintos niveles de digitalización, conectividad y capacidad tecnológica. En consecuencia, la información de un mismo paciente puede generarse en diferentes sistemas, dispositivos y momentos, con diferentes estructuras, frecuencias, latencias y niveles de calidad. 

Por tanto, el desafío de RISA no consiste únicamente en aplicar un algoritmo de Machine Learning sobre un conjunto de datos estructurado. El problema central es **transformar información fragmentada, heterogénea y temporal en señales de riesgo que puedan ser interpretadas, priorizadas y verificadas**.

---

### 1.1.2. Naturaleza de los datos

RISA Data V1.0 integra diferentes categorías de información:

* datos maestros de pacientes, encuentros, establecimientos y dispositivos;
* antecedentes y condiciones clínicas;
* resultados de laboratorio;
* administración de medicamentos;
* signos vitales;
* observaciones provenientes de wearables;
* observaciones de dispositivos;
* contexto del paciente;
* eventos de conectividad;
* metadatos sobre variables, fuentes y unidades.

Estas fuentes no necesariamente poseen la misma granularidad ni frecuencia, por lo que una parte fundamental del problema consiste en **reconstruir la historia temporal del paciente a partir de múltiples tablas**. Además, los identificadores originales deben conservarse para permitir integración, auditoría y trazabilidad. 

---

### 1.1.3. La temporalidad como dimensión fundamental

Una característica central del escenario es que el momento en que ocurre un fenómeno no necesariamente coincide con el momento en que la información se encuentra disponible para el sistema.

Por ejemplo, un resultado de laboratorio puede corresponder a una muestra obtenida en un instante determinado, pero estar disponible posteriormente. De forma similar, una observación de un wearable puede producirse antes de que sea sincronizada con el sistema. 

Por ello, la solución deberá diferenciar conceptualmente:

$$
T_{event}
$$

momento en que ocurre el fenómeno, de:

$$
T_{available}
$$

momento en que la información está disponible para ser utilizada.

Para una decisión tomada en un instante \(T\), solamente podrá utilizarse evidencia que cumpla:

$$
T_{available} \leq T
$$

Esta restricción será fundamental durante la construcción de características, generación de baselines, entrenamiento y validación de los modelos, con el objetivo de evitar **temporal leakage**. 

---

## 1.2. Definición del problema

### 1.2.1. Problema general

El problema de RISA no es la ausencia de información, sino la **fragmentación, heterogeneidad, frecuencia variable, latencia y calidad desigual de los datos**. 

En consecuencia, una observación individual no necesariamente contiene suficiente información para determinar si una situación requiere atención.

Por ejemplo, un valor fisiológico elevado podría representar:

* una variación transitoria;
* una respuesta esperada a una actividad;
* un artefacto de medición;
* un problema de conectividad;
* una señal que adquiere importancia al combinarse con otras variables;
* una tendencia progresiva.

Por esta razón, el reto plantea una pregunta operativa central:

> **¿Cómo reconocer oportunamente que una combinación de datos merece atención, sin convertir cada variación en una alerta?** 

---

### 1.2.2. Formulación del problema de ingeniería

Desde la perspectiva de ingeniería de datos e inteligencia artificial, el problema puede formularse como:

> **Diseñar un sistema capaz de integrar múltiples fuentes heterogéneas y temporales, identificar comportamientos inusuales, reconocer patrones relevantes, incorporar contexto y calidad de datos, y transformar estas evidencias en señales de riesgo priorizadas, explicables y trazables, sin utilizar información que no estuviera disponible en el momento de la decisión.**

Esta formulación es importante porque evita reducir el reto a:

> "predecir riesgo mediante Machine Learning".

El sistema propuesto debe resolver un problema más amplio:

```text
Datos heterogéneos
       ↓
Integración
       ↓
Temporalidad + calidad
       ↓
Contexto
       ↓
Anomalías
       ↓
Patrones
       ↓
Evidencia
       ↓
Riesgo
       ↓
Prioridad
       ↓
Explicación
```

Este flujo está alineado con el principio central del reto: transformar datos heterogéneos en señales oportunas y priorizadas, sustentadas en evidencia disponible en el momento de decisión y trazables hasta los registros fuente. 

---

## 1.2.3. Problemas específicos

A partir del problema general se identifican los siguientes subproblemas.

### A. Integración de fuentes heterogéneas

Los datos provenientes de sistemas clínicos, dispositivos, wearables, laboratorios y fuentes contextuales poseen diferentes estructuras, frecuencias y características.

El sistema debe determinar:

> ¿Qué registros corresponden al mismo paciente y qué información describe el mismo episodio o ventana temporal?

---

### B. Comprensión temporal

Una señal relevante puede no estar determinada por un valor aislado, sino por:

* tendencia;
* persistencia;
* cambio;
* velocidad de cambio;
* secuencia;
* combinación de variables.

RISA está diseñada precisamente para que la situación no siempre pueda comprenderse mediante una única observación. 

---

### C. Detección de anomalías

Debe determinarse si una observación o conjunto de observaciones representa un comportamiento inusual respecto al comportamiento esperado.

Sin embargo:

$$
\text{Anomalía} \neq \text{Riesgo}
$$

Una anomalía puede ser causada por un problema de calidad, una variación temporal o un contexto perfectamente explicable.

Por ello, la arquitectura incorpora un **Anomaly Model** independiente.

---

### D. Identificación de patrones relevantes

No basta con detectar valores extremos.

El sistema debe determinar si existe un **patrón temporal o multivariable** que justifique una señal.

Por ejemplo, un cambio moderado pero sostenido en varias variables puede ser más relevante que un valor extremo aislado. 

Para esto se incorpora el **Pattern Model**, cuyo algoritmo será seleccionado experimentalmente entre alternativas estadísticas, ML y DL.

---

### E. Interpretación contextual

El mismo comportamiento fisiológico puede tener diferentes interpretaciones dependiendo del contexto.

Por ejemplo:

```text
HR elevada
     +
actividad física
```

no debería interpretarse necesariamente igual que:

```text
HR elevada
     +
reposo
```

Por ello se incorpora un **Context Engine**, que podrá utilizar reglas, métodos estadísticos, ML, NLP/LLM o una estrategia híbrida dependiendo de los resultados experimentales.

---

### F. Calidad de los datos

RISA incorpora intencionalmente:

* valores faltantes;
* duplicados;
* retransmisiones;
* ruido;
* outliers;
* diferentes unidades;
* diferentes frecuencias;
* desalineación temporal;
* problemas de conectividad.

La presencia de un valor extremo no implica automáticamente que exista una situación de riesgo. 

Por tanto, la calidad debe constituir una dimensión explícita de la arquitectura.

---

### G. Priorización

La solución no debe limitarse a identificar señales.

Debe responder:

> **¿Qué situación debería revisarse primero y por qué?**

El reto exige que la solución permita ordenar pacientes o señales de forma operativa y justificar por qué una situación tiene mayor prioridad que otra. 

---

### H. Explicabilidad y trazabilidad

Toda señal generada debe poder responder:

* qué ocurrió;
* cuándo ocurrió;
* qué variables participaron;
* qué contexto existía;
* qué evidencia fue utilizada;
* por qué se asignó determinado nivel de prioridad;
* de qué registros originales provino la evidencia.

La cadena conceptual requerida es:

$$
Dato \rightarrow Evidencia \rightarrow Señal \rightarrow Prioridad \rightarrow Explicación
$$

manteniendo también la posibilidad de recorrerla en sentido inverso para auditoría. 

---

# 1.3. Objetivos

## 1.3.1. Objetivo general

> **Desarrollar una solución inteligente para RISA capaz de transformar datos de salud heterogéneos, temporales y de calidad variable en señales de riesgo oportunas, priorizadas, explicables y trazables, mediante la integración de detección de anomalías, reconocimiento de patrones, análisis contextual y fusión de evidencias.**

La solución tendrá como finalidad **apoyar la identificación, priorización y revisión de situaciones relevantes**, sin realizar diagnósticos ni prescripciones autónomas. 

---

## 1.3.2. Objetivos específicos

### OE1. Integrar las fuentes de RISA

Construir un pipeline capaz de integrar las diferentes fuentes manteniendo los identificadores originales y preservando la procedencia de los datos.

### OE2. Construir una representación temporal del paciente

Reconstruir la evolución del paciente mediante la integración de observaciones, eventos clínicos, contexto y disponibilidad temporal.

### OE3. Gestionar la calidad de los datos

Identificar y tratar adecuadamente missingness, duplicados, ruido, valores sospechosos, unidades, desalineación temporal y problemas de conectividad.

### OE4. Detectar comportamientos anómalos

Implementar y comparar diferentes estrategias de detección de anomalías, desde métodos estadísticos hasta ML/DL, seleccionando la alternativa que presente el mejor equilibrio entre detección, falsas alertas, robustez y complejidad.

### OE5. Identificar patrones relevantes

Evaluar diferentes modelos de Machine Learning y Deep Learning para determinar cuál permite reconocer mejor patrones temporales y multivariables relevantes.

### OE6. Incorporar contexto

Desarrollar un mecanismo capaz de utilizar información contextual y de calidad para modificar la interpretación de las señales detectadas.

### OE7. Fusionar evidencias

Combinar anomalías, patrones, contexto y calidad para generar una representación integrada de la situación.

### OE8. Generar un nivel de riesgo y prioridad

Transformar la evidencia integrada en un `risk_score` y un nivel de prioridad:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

La especificación oficial de `signals.csv` contempla un `risk_score` entre 0 y 1 y estos cuatro niveles de prioridad. 

### OE9. Generar explicaciones verificables

Proporcionar explicaciones fundamentadas exclusivamente en la evidencia disponible, sin inventar mediciones, antecedentes o hechos.

### OE10. Garantizar trazabilidad

Permitir recorrer una señal hasta las fuentes y registros que la originaron mediante `evidence.csv`.

### OE11. Evaluar la solución bajo diferentes escenarios

Evaluar la solución considerando situaciones normales, transitorias, contextuales, progresivas, multisource, problemas de calidad y escenarios complejos.

### OE12. Garantizar reproducibilidad

Construir un pipeline ejecutable y reproducible capaz de producir los resultados estructurados exigidos por el reto.

---

# 1.4. Alcance

## 1.4.1. Alcance funcional

La solución abarcará las siguientes capacidades:

```text
                     RISA DATA
                         │
                         ▼
                  DATA INTEGRATION
                         │
                         ▼
                 TEMPORAL ALIGNMENT
                         │
                         ▼
                  DATA QUALITY
                         │
                         ▼
              PATIENT REPRESENTATION
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       ANOMALY         PATTERN        CONTEXT
        MODEL           MODEL         ENGINE
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  EVIDENCE FUSION
                         │
                         ▼
                    RISK ENGINE
                         │
                         ▼
                  PRIORITY ENGINE
                         │
                         ▼
                    EXPLANATION
                         │
                         ▼
              SIGNAL + EVIDENCE OUTPUT
```

---

## 1.4.2. Anomaly Model

El componente de anomalías tendrá como objetivo determinar si una observación o conjunto de observaciones presenta un comportamiento inusual.

Se evaluarán diferentes familias de métodos:

```text
Estadística
├── Z-score
├── MAD
└── IQR

ML
├── Isolation Forest
└── LOF

DL
└── Autoencoder
```

La selección final no estará predeterminada.

---

## 1.4.3. Pattern Model

El Pattern Model determinará si existe un patrón temporal o multivariable relevante.

Se evaluarán, según disponibilidad y características de los datos:

```text
Baseline
└── Logistic Regression

ML
├── Random Forest
├── XGBoost
└── LightGBM

DL
├── GRU
├── LSTM
└── Transformer temporal
```

La selección se realizará experimentalmente utilizando métricas de detección, anticipación, falsas alertas, robustez e interpretabilidad.

Por tanto, **XGBoost y GRU serán candidatos, no supuestos de diseño**.

---

## 1.4.4. Context Engine

El Context Engine tendrá como finalidad incorporar información que permita interpretar las señales detectadas.

Se contemplan:

```text
Reglas
+
Machine Learning
+
NLP/LLM
+
Estrategias híbridas
```

La complejidad del componente dependerá de la naturaleza de los datos y del resultado de los experimentos.

---

## 1.4.5. Evidence Fusion

El sistema combinará:

* evidencia primaria;
* evidencia de soporte;
* evidencia contextual;
* evidencia relacionada con calidad.

La especificación oficial reconoce precisamente estos roles:

```text
PRIMARY
SUPPORTING
CONTEXT
QUALITY
```

para los elementos de evidencia. 

---

## 1.4.6. Risk y Priority Engine

La solución transformará la evidencia fusionada en:

$$
RiskScore \in [0,1]
$$

y posteriormente en una prioridad operativa.

El objetivo no será maximizar el número de alertas, sino **maximizar la pertinencia de las señales generadas**.

---

## 1.4.7. Explicabilidad

Las explicaciones deberán estar sustentadas en la evidencia utilizada por el sistema.

Un LLM, si se utiliza, podrá transformar evidencia estructurada en lenguaje natural, pero no podrá generar hechos que no estén presentes en los datos. 

---

## 1.4.8. Trazabilidad

Cada señal deberá poder relacionarse con:

```text
signal_id
   ↓
patient_id
   ↓
decision_datetime
   ↓
evidence window
   ↓
source_file
   ↓
record_id
   ↓
variable_code
   ↓
event_datetime
   ↓
available_datetime
```

La estructura oficial de `evidence.csv` contempla precisamente estos elementos. 

---

# 1.4.9. Límites del proyecto

La solución **no tendrá como objetivo**:

* realizar diagnósticos médicos;
* prescribir tratamientos;
* sustituir la decisión de profesionales;
* generar decisiones clínicas autónomas;
* utilizar información futura respecto al momento de decisión;
* alterar los archivos originales de RISA Data V1.0.

El reto establece que RISA debe utilizarse como mecanismo de apoyo para identificación, priorización y revisión, y no como sistema autónomo de diagnóstico o prescripción. 

Los archivos oficiales deben considerarse inmutables, aunque sí pueden generarse copias, datos derivados, Parquet, features, índices o embeddings. 

---

# 1.5. Criterios de éxito

Esta sección debe ser especialmente rigurosa porque servirá posteriormente para decidir **qué modelo es mejor** y para demostrar que la arquitectura completa funciona.

No propondría como criterio:

> "El modelo con mayor accuracy gana."

El éxito de RISA es multidimensional.

---

## 1.5.1. Detección

La solución debe identificar señales relevantes y no simplemente valores fuera de rango.

Se evaluará mediante métricas como:

* Precision;
* Recall;
* F1;
* PR-AUC cuando existan etiquetas apropiadas.

---

## 1.5.2. Anticipación

La solución debe ser capaz de producir una señal en un momento útil sin utilizar información futura.

Se evaluará mediante:

$$
LeadTime =
T_{event/relevance}-T_{decision}
$$

y mediante la validación de:

$$
T_{available} \leq T_{decision}
$$

La anticipación es una capacidad explícitamente requerida por RISA. 

---

## 1.5.3. Control de falsas alertas

Una solución que genera demasiadas alertas pierde utilidad operacional.

Por tanto se evaluará:

$$
FalseAlertRate =
\frac{FalseAlerts}{TotalAlerts}
$$

junto con Precision y la proporción de situaciones normales correctamente relegadas.

Esto es particularmente importante porque RISA contiene deliberadamente variaciones que pueden parecer preocupantes pero que no deberían convertirse automáticamente en alertas prioritarias. 

---

## 1.5.4. Priorización

El sistema debe ser capaz de ordenar las señales de acuerdo con su relevancia.

Se deberá poder responder:

> **¿Por qué el paciente A aparece antes que el paciente B?**

El ranking debe estar sustentado en variables, evolución temporal y evidencia.

---

## 1.5.5. Robustez

La solución debe mantener un comportamiento razonable ante:

* missingness;
* ruido;
* outliers;
* datos duplicados;
* retrasos;
* diferentes frecuencias;
* problemas de conectividad;
* ausencia parcial de fuentes.

Estos problemas forman parte intencional del escenario RISA. 

---

## 1.5.6. Calidad de la interpretación contextual

El Context Engine debe evitar interpretar una variación de manera aislada cuando existe información contextual relevante.

Por ejemplo:

```text
Variación fisiológica
        +
actividad
        ↓
interpretación contextual
```

frente a:

```text
Variación fisiológica
        +
reposo
        ↓
interpretación diferente
```

---

## 1.5.7. Explicabilidad

Cada señal debe poder explicar:

```text
QUÉ
↓
CUÁNDO
↓
QUÉ CAMBIÓ
↓
QUÉ VARIABLES PARTICIPARON
↓
QUÉ CONTEXTO EXISTÍA
↓
QUÉ CALIDAD TENÍAN LOS DATOS
↓
POR QUÉ SE PRIORIZÓ
```

La explicación debe ser breve, verificable y sustentada en evidencia.

---

## 1.5.8. Trazabilidad

Una señal será considerada correctamente sustentada cuando pueda recorrerse la ruta:

```text
Signal
   ↓
Evidence
   ↓
Source file
   ↓
Original record
```

El reto exige conservar esta trazabilidad y que las señales puedan regresar a los registros que las originaron. 

---

## 1.5.9. Reproducibilidad

La solución deberá:

* tener un punto de entrada claro;
* utilizar rutas configurables;
* conservar versiones;
* producir resultados estructurados;
* permitir reconstruir las señales;
* mantener consistencia entre `signals.csv` y `evidence.csv`.

Estos requisitos forman parte explícita de la entrega técnica. 

---

# 1.5.10. Criterio global de éxito

Finalmente, propondría definir el éxito de la solución mediante cinco dimensiones principales:

| Dimensión                         | Pregunta                                                   |
| --------------------------------- | ---------------------------------------------------------- |
| **Detection**                     | ¿Detectamos señales realmente relevantes?                  |
| **Anticipation**                  | ¿Las detectamos suficientemente temprano?                  |
| **Pertinence**                    | ¿Evitamos alertas innecesarias?                            |
| **Robustness**                    | ¿Funcionamos ante ruido, missingness, contexto y latencia? |
| **Explainability & Traceability** | ¿Podemos demostrar por qué generamos cada señal?           |

Por tanto, conceptualmente:

$$
Success =
Detection+
Anticipation+
Pertinence+
Robustness+
Traceability
$$

No se trata de una fórmula matemática para obtener el score final del hackathon, sino del **marco de evaluación de ingeniería** que guiará la selección de modelos y la evaluación de la solución.

---

# Resultado del Punto 1

Al terminar esta primera fase, la arquitectura queda justificada de esta manera:

```text
                       PROBLEMA RISA
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   ¿Es inusual?      ¿Hay un patrón?     ¿Qué contexto?
        │                   │                   │
        ▼                   ▼                   ▼
   ANOMALY MODEL       PATTERN MODEL      CONTEXT ENGINE
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                     EVIDENCE FUSION
                            │
                            ▼
                       RISK ENGINE
                            │
                            ▼
                     PRIORITY ENGINE
                            │
                            ▼
                       EXPLANATION
                            │
                            ▼
                 SIGNAL + EVIDENCE
```

Y lo más importante para las siguientes fases es que **el Punto 1 no decide todavía qué algoritmo utilizar**. Define el problema y los criterios con los que posteriormente podremos demostrar por qué, por ejemplo, **Isolation Forest supera a LOF para anomalías**, o por qué **XGBoost supera a GRU**, o incluso por qué una solución basada en reglas resulta suficiente para una parte del Context Engine.

Eso permite que el **Punto 2 — Comprensión de los datos** sea completamente objetivo: ahora debemos abrir el dataset, caracterizar las fuentes, reconstruir relaciones, estudiar la temporalidad, disponibilidad, calidad y distribución de los datos, y **solo después** pasar al diseño experimental de los tres componentes.

## Arquitectura
                         RISA DATA
                            │
                            ▼
                  ┌─────────────────┐
                  │ DATA FUSION     │
                  │ temporal align  │
                  │ normalization   │
                  │ quality         │
                  └────────┬────────┘
                           │
                           ▼
                 PATIENT DIGITAL BASELINE
                           │
                           ▼
                    TEMPORAL FEATURES
                           │
            ┌──────────────┼───────────────┐
            ▼              ▼               ▼
      Anomaly Model   Pattern Model   Context Engine
                           │
                           ▼
                  MODEL SELECTION
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
       Candidate ML                 Candidate DL
             │                           │
       ┌─────┼─────┐              ┌─────┼─────┐
       ▼     ▼     ▼              ▼     ▼     ▼
      LR     RF   XGBoost         GRU   LSTM Transformer
       │     │     │              │     │     │
       └─────┴─────┘              └─────┴─────┘
             │                           │
             └─────────────┬─────────────┘
                           ▼
                    MODEL EVALUATION
                           │
                           ▼
                    SELECTED MODEL
                           │
                           ▼
                    EVIDENCE FUSION
                           │
                           ▼
                      RISK ENGINE
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                Risk Score    Confidence
                    │             │
                    └──────┬──────┘
                           ▼
                    PRIORITY ENGINE
                           │
                           ▼
                      EXPLANATION
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                  SHAP            LLM
                    │             │
                    └──────┬──────┘
                           ▼
                       DASHBOARD
### Anomaly model
                 Anomaly Model Selection
                          │
                          ▼
                 Data characterization
                          │
                          ▼
                  Candidate methods
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
         Statistical      ML           DL
             │            │            │
          MAD/IQR     IF/LOF       Autoencoder
             │            │            │
             └────────────┼────────────┘
                          ▼
                  Scenario testing
                          │
                          ▼
                  Synthetic testing
                          │
                          ▼
                  False Alert Analysis
                          │
                          ▼
                     Robustness
                          │
                          ▼
                 Selected Anomaly Model

### context engine
                CONTEXT ENGINE
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Rules        Ontology       ML/NLP
          │            │            │
          ▼            ▼            ▼
      Temporal     Context        Context
      matching     mapping       extraction
          │            │            │
          └────────────┼────────────┘
                       ▼
                  Context Score



                    Context
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     Structured     Temporal       Text
          │            │            │
       Rules/ML     ML/DL        NLP/LLM

### para los tres modelos
                        RISA
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
       Anomaly Model  Pattern Model  Context Engine
             │            │            │
             ▼            ▼            ▼
         Selection     Selection     Selection
             │            │            │
             ▼            ▼            ▼
        Best anomaly  Best predictor Best context
             │            │            │
             └────────────┼────────────┘
                          ▼
                    Evidence Fusion