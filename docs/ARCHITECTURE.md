# Arquitectura de AeroLink

## Flujo

`DJI Pilot 2 → HTTPS/MQTTS → relay externo → (conexión saliente) → AeroLink en
p340 → PostgreSQL/objeto → interfaz AeroLink`

El relay aparece en el flujo por el veredicto del gate de red: ver
[ADR-0004](adr/0004-broker-mqtt-en-relay-externo.md).

## Servicios

- `aerolink-api`: FastAPI, H5 de Pilot 2, administración y API interna.
- `aerolink-worker`: cliente MQTT del relay, normalización y detección de vuelos.
- `postgres`: datos operacionales, estados y auditoría.
- `relay MQTT externo`: broker MQTTS con ingreso público real, autenticación
  individual y ACL por dispositivo. **No corre en p340** (ADR-0004); el servicio
  `emqx` de `docker-compose.yml` es solo para desarrollo local.
- `object-storage`: MinIO o S3-compatible privado para logs y evidencia.

Todos, salvo el relay, se despliegan en p340 con redes y volúmenes separados de
AeroControl. AeroLink no abre conexiones a la base de datos ni al filesystem de
AeroControl.

## Datos propios

Existen como tabla y tienen quién las escriba:

- `Workspace`, `Device` (AL-107), `RawMessage` (el worker), `FlightEvidence`
  (AL-105) y `AuditEvent`.

Existen como tabla y **todavía sin escritor**, con el trabajo que lo traerá:

- `UserIdentity` — AL-103, bloqueada por la decisión de identidad (AL-R6).
- `TelemetrySample` y `FlightSession` — AL-301/AL-302, después de que AL-204
  capture fixtures reales de DJI.
- `IngestionException` — la bandeja de AL-306. `/metrics` ya publica cuántas hay
  abiertas; hoy son cero porque nada las crea, y el primer escritor honesto
  aparece con la normalización de AL-302.

`DeviceTopology` **no existe**: ni modelo, ni tabla, ni referencias. Llega con
AL-203, que es donde se registra la topología control–aeronave–payload.

Los identificadores son UUID. Cada sesión conserva un identificador externo
inmutable para permitir una integración futura sin cambiar el histórico.

## Seguridad

- Microsoft Entra ID con identidades individuales.
- Roles Administrator, Operations, Pilot y Viewer.
- TLS público válido para HTTPS y MQTTS.
- Sin usuarios MQTT anónimos.
- Credenciales por control, revocables y rotables.
- Secretos fuera de Git.
- Evidencias con SHA-256 y auditoría de descarga.

## Observabilidad

Dos exposiciones Prometheus, porque son dos procesos:

- `aerolink-api` en `/metrics`: latencia y conteo HTTP, más los indicadores de
  ingesta leídos de la base de datos —mensajes almacenados, marca de tiempo del
  último recibido, excepciones abiertas—. Sobreviven al reinicio del worker, que es
  justo cuando alguien pregunta qué pasó. Si la base no responde, el scrape sigue
  en pie y baja `aerolink_ingestion_metrics_available` a 0.
- `aerolink-worker` en su propio puerto (`WORKER_METRICS_PORT`, publicado en
  `127.0.0.1:8093` en desarrollo): mensajes persistidos y acusados, fallos de
  persistencia, conexiones al relay etiquetadas por si el relay **conservaba
  nuestra sesión**, y desconexiones.

Las dos alertas que importan antes del primer vuelo: ingesta detenida
(`time() - aerolink_raw_message_last_received_timestamp_seconds` sobre el umbral) y
`aerolink_worker_relay_connections_total{session="new"}` creciendo después de la
primera conexión — el relay perdió la cola que el worker daba por guardada.

Las sondas fallan rápido a propósito: el motor de base de datos se abre con
`connect_timeout`, porque sin él un host que no resuelve deja `/ready` y `/metrics`
colgados el timeout completo del sistema (~130 s medidos) en vez de responder 503
o `available 0`.

## Retención

- Telemetría detallada: 90 días.
- Vuelos, eventos relevantes, logs originales y hashes: 5 años.
- Retención configurable mediante variables de entorno.

## Gate de red

**Resuelto con veredicto negativo el 2026-08-10 (AL-003).** Medido desde fuera de
la red Tailscale contra la IP pública de p340 (`200.54.29.98`): ni 443 ni 8883
aceptan TCP entrante. Tailscale Funnel no abre puertos en esa IP —tunela saliente
hacia el relay de Tailscale— y sirve HTTPS solamente, así que **ningún control DJI
puede alcanzar un broker alojado en p340**.

Camino adoptado: broker en un **relay externo** con IP pública propia, con p340 como
cliente saliente. Detalle, opciones descartadas y consecuencias en
[ADR-0004](adr/0004-broker-mqtt-en-relay-externo.md). Sigue pendiente elegir el
proveedor del relay; hasta entonces `AL-R1` no se cierra.

Lo que entra por HTTPS (`/health`, `/ready`, la H5 de Pilot 2 y el inventario de
`AL-107`) no está afectado: Funnel ya lo sirve.

