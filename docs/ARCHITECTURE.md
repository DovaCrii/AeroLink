# Arquitectura de AeroLink

## Flujo

`DJI Pilot 2 → HTTPS/MQTTS → AeroLink → PostgreSQL/objeto → interfaz AeroLink`

## Servicios

- `aerolink-api`: FastAPI, H5 de Pilot 2, administración y API interna.
- `aerolink-worker`: consumidor MQTT, normalización y detección de vuelos.
- `postgres`: datos operacionales, estados y auditoría.
- `emqx`: broker MQTTS con autenticación individual y ACL por dispositivo.
- `object-storage`: MinIO o S3-compatible privado para logs y evidencia.

Todos se despliegan en p340 con redes y volúmenes separados de AeroControl.
AeroLink no abre conexiones a la base de datos ni al filesystem de AeroControl.

## Datos propios

- `Workspace` y `UserIdentity`.
- `Device` y `DeviceTopology`.
- `RawMessage` y `TelemetrySample`.
- `FlightSession`.
- `FlightEvidence`.
- `IngestionException`.
- `AuditEvent`.

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

## Retención

- Telemetría detallada: 90 días.
- Vuelos, eventos relevantes, logs originales y hashes: 5 años.
- Retención configurable mediante variables de entorno.

## Gate de red

Antes de M1 se debe confirmar si p340 puede recibir HTTPS 443 y MQTTS 8883.
Si solo existe Tailscale Funnel y el hardware no admite MQTT sobre WSS
compatible, se debe habilitar NAT/IP pública o un relay MQTT externo.

