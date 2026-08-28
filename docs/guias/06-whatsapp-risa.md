# WhatsApp RISA

Este módulo conecta un único número de WhatsApp Business Cloud API con dos funciones independientes:

1. Notificaciones automáticas filtradas, activas mientras el backend está encendido.
2. Chat con el agente RISA cuando el usuario escribe `RISA`.

Es un prototipo de apoyo a revisión. No sustituye atención clínica, diagnóstico ni emergencias.

## Requisitos de Meta

`WHATSAPP_APP_ID`, `WHATSAPP_APP_SECRET` y `WHATSAPP_CONFIG_ID` no bastan para enviar mensajes. En Meta for Developers > WhatsApp > API Setup hay que obtener:

- `WHATSAPP_PHONE_NUMBER_ID`: identificador del único número emisor.
- `WHATSAPP_WABA_ID`: identificador de la cuenta de WhatsApp Business.
- `WHATSAPP_ACCESS_TOKEN`: token permanente de usuario del sistema con `whatsapp_business_messaging` y `whatsapp_business_management`.
- `WHATSAPP_VERIFY_TOKEN`: secreto elegido localmente para el challenge del webhook.

Nunca se deben pegar secretos en documentación, Git o conversaciones.

## Configuración

Copiar las variables WhatsApp de `backend/.env.example` a `backend/.env`. Para comenzar:

```env
WHATSAPP_ENABLED=true
WHATSAPP_DRY_RUN=true
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_WABA_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_VERIFY_TOKEN=un-secreto-largo-propio
WHATSAPP_ADMIN_TOKEN=otro-secreto-administrativo
PATIENT_CONTACTS_CSV=.runtime/private/patient_contacts.csv

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_VERIFY_SERVICE_SID=
TWILIO_DRY_RUN=true
```

En modo simulado no salen mensajes reales. Cuando challenge, contactos y pruebas estén correctos, completar los IDs/token y cambiar `WHATSAPP_DRY_RUN=false`.

Twilio Verify requiere crear un Verify Service en la consola de Twilio. Para SMS reales, completar sus tres credenciales, cambiar `TWILIO_DRY_RUN=false` y reiniciar. En simulación el OTP de prueba es `000000`.

### Preparar Twilio Verify

1. Crear una cuenta en Twilio y abrir `Verify > Services`.
2. Crear un servicio llamado `RISA Patient Verification`.
3. Copiar su SID `VA...` en `TWILIO_VERIFY_SERVICE_SID`.
4. Copiar Account SID `AC...` y Auth Token desde la consola.
5. En cuentas trial, verificar previamente el número de destino si Twilio lo exige.
6. Ejecutar:

```powershell
python -m app.whatsapp.cli twilio-status
```

El resultado debe mostrar `live_ready: true` y `dry_run: false` antes de esperar un SMS real.

## Webhook local

Ejecutar el backend en el puerto alternativo:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Publicar `http://127.0.0.1:8010` mediante Cloudflare Tunnel o ngrok. En Meta configurar:

- Callback URL: `https://DOMINIO-PUBLICO/api/whatsapp/webhook`
- Verify token: el mismo `WHATSAPP_VERIFY_TOKEN`
- Suscripción: campo `messages`

La aplicación valida `X-Hub-Signature-256` con `WHATSAPP_APP_SECRET`. El túnel y Uvicorn deben seguir encendidos; para disponibilidad real se necesita desplegar el backend en un servidor persistente.

## Plantilla de notificación

Fuera de la ventana de atención de 24 horas Meta exige una plantilla aprobada. Crear una plantilla `UTILITY` llamada como `WHATSAPP_TEMPLATE_NAME`, idioma `es`, con dos variables:

```text
RISA tiene {{1}} actualización(es) de seguimiento. Prioridad operativa: {{2}}.
Responde RISA para iniciar una consulta autorizada. Si es una emergencia, usa los canales de atención habituales.
```

La plantilla evita diagnóstico, evidencia o valores clínicos sensibles. Los detalles solo se consultan después de que la persona abre la conversación. Si la plantilla incluye un quick reply `Ver alertas`, configurar `WHATSAPP_TEMPLATE_QUICK_REPLY=true`.

## SQLite clínico y teléfono privado

El importador sincroniza en SQLite todos los CSV disponibles, alertas y procedencia. La fuente sigue siendo el pipeline:

```powershell
python -m app.whatsapp.cli sync-clinical-data
```

Los teléfonos viven exclusivamente en `.runtime/private/patient_contacts.csv`, excluido de Git:

```csv
patient_id,phone_e164,timezone,clinical_contact_phone
PAT-0724,+51946153327,America/Lima,
```

El dataset RAW no contiene teléfonos. No se debe enviar SMS a un número escrito por el usuario: siempre se usa el teléfono oficial importado.

## Autorregistro con SMS

Desde el número oficial asociado, el paciente envía:

```text
PAT-0724
```

RISA compara el número de WhatsApp con SQLite y Twilio Verify envía un OTP por SMS. El paciente copia el OTP al chat y confirma mediante los botones `Acepto` o `Cancelar`. Solo entonces se vincula el contacto, se habilitan notificaciones y se abre la sesión. El OTP no se guarda en SQLite.

Para este prototipo el único vínculo privado es `PAT-0724` con `+51946153327`. Cualquier otro PAT-ID o teléfono obtiene una respuesta genérica.

El personal clínico se asigna administrativamente:

```powershell
python -m app.whatsapp.cli register --phone +593988888888 --role clinician --patient PAT-0724 --patient PAT-0290 --timezone America/Guayaquil --opt-in
```

Sin `--opt-in` no se envían notificaciones. Para retirar consentimiento:

```powershell
python -m app.whatsapp.cli consent --phone +593999999999 --enabled no
```

Un paciente no puede consultar otro PAT-ID. El personal clínico solo puede consultar su lista asignada. Esta autorización se intersecta con el Planner, RAG, tools, texto y RISA UI.

## Interacción móvil

- `RISA`: abre una sesión de chat durante 24 horas.
- `PAT-XXXX`: inicia la validación por SMS si número y paciente coinciden.
- `AYUDA`: muestra una lista interactiva.
- `GRAFICO frecuencia cardíaca del último mes`: solicita una imagen PNG.
- `SALIR`: cierra el chat; no cancela notificaciones autorizadas.
- `BAJA`: cancela notificaciones y cierra la sesión.

El menú principal utiliza tres botones oficiales: `Ver alertas`, `Constantes` e `Informe PDF`. Después de una alerta aparecen `Ver detalle`, `Confirmar lectura` y `Contactar médico`. Los botones solo se envían dentro de una ventana de atención abierta, salvo quick replies aprobados dentro de plantillas.

Las respuestas se convierten a formato nativo de WhatsApp, se dividen en burbujas breves y traducen variables técnicas sin inventar significado clínico.

Las notificaciones no dependen de que exista una sesión de chat.

## Filtro anti-spam

El escáner conserva un baseline y no envía en masa al arrancar. Solo considera:

- `CRITICAL` y `HIGH`.
- `MEDIUM` cuando risk score supera el umbral y anomaly/pattern coinciden.
- Alertas nuevas, cambios relevantes o escalamiento.

También aplica fingerprint, deduplicación, cooldown, máximo diario, horario silencioso y digest por destinatario. Un escalamiento puede saltar una vez el cooldown. `LOW`, `BAJO` y `DESCARTADO` no producen notificación automática.

Para una demostración explícita del snapshot inicial:

```powershell
python -m app.whatsapp.cli scan --include-baseline
```

Sin esa opción, el primer escaneo solo establece baseline.

## Trazabilidad

SQLite registra mensajes entrantes/salientes, IDs de Meta, estados `sent`, `delivered`, `read` o `failed`, plan, alcance, citas, advertencias, tools y procedencia de gráficos.

```powershell
python -m app.whatsapp.cli audit --phone +51946153327 --limit 20
```

La salida se redacta por defecto; `--include-content` debe usarse solo en diagnóstico local autorizado. La base predeterminada está en `backend/.runtime/whatsapp.sqlite3` y está excluida de Git.

## Gráficos

El backend convierte localmente los Plotly specs del agente a PNG sin enviar datos a un servicio externo. Las barras por nivel mantienen colores semánticos. WhatsApp admite PNG/JPEG; el módulo limita a dos imágenes por respuesta y 5 MB por archivo. Si falla la conversión, conserva la respuesta textual y registra el error.

## Informe PDF y contacto

El botón `Informe PDF` genera localmente un documento limitado al paciente autenticado con perfil mínimo, alertas, últimas constantes, laboratorios, procedencia y descargo clínico. Se sube como documento a Meta y no se guarda en disco.

`Contactar médico` utiliza primero `clinical_contact_phone` del registro privado y luego `CLINICAL_CONTACT_PHONE`. Si ninguno existe, muestra una advertencia y no inventa un contacto.
