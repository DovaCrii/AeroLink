# AeroLink — Plan maestro

## Objetivo

Construir una plataforma independiente que reciba información de DJI Pilot 2,
identifique equipos y operadores autenticados, reconstruya vuelos y conserve
telemetría y evidencia técnica sin depender de planillas de terreno.

## Límites de la primera versión

- Una combinación de aeronave, control y firmware para el piloto inicial.
- Solo lectura y registro.
- Sin comandos remotos.
- Sin generación o envío de misiones DJI.
- Sin integración de código, API ni base de datos con AeroControl.
- La integración futura será un proyecto separado dentro del repositorio
  `DovaCrii/AeroControl`.

## Flota interna confirmada

- DJI Mavic 3 Enterprise (Mavic 3E).
- DJI Matrice 4 Enterprise (Matrice 4E).
- DJI Matrice 4 Thermal (Matrice 4T).

La selección del piloto sigue pendiente: debe validarse la combinación exacta
de aeronave, control, firmware y versión de DJI Pilot 2 contra los requisitos
vigentes de DJI Cloud API. No se asume compatibilidad por el modelo de aeronave.

## Milestones

| Milestone | Resultado | Dependencia |
|---|---|---|
| M0 | Inventario, Cloud API, red, DNS y gate de viabilidad | Ninguna |
| M1 | Backend, worker, PostgreSQL, EMQX, almacenamiento y CI | M0 |
| M2 | H5 de Pilot 2, licencia, workspace y conexión MQTT | M1 |
| M3 | Telemetría normalizada, sesiones de vuelo, evidencia y dashboard | M2 |
| M4 | Piloto controlado, pruebas de recuperación y runbooks | M3 |

## Issues iniciales

### M0 — Descubrimiento y viabilidad

- AL-001 Inventario de aeronaves, controles, firmware, Pilot 2 y payloads.
- AL-002 Selección de combinación DJI para el piloto.
- AL-003 Validación de ingreso público p340, DNS, TLS, HTTPS y MQTT.
- AL-004 Registro de aplicación y licencia DJI Cloud API.
- AL-005 ADR de arquitectura, amenazas, retención y respaldos.

### M1 — Plataforma

- AL-101 Scaffold FastAPI, worker, Docker Compose y CI.
- AL-102 PostgreSQL, migraciones y modelo de datos.
- AL-103 Microsoft Entra ID, roles y auditoría.
- AL-104 EMQX con TLS, autenticación, rotación y ACL.
- AL-105 Almacenamiento de evidencias, hashes, retención y backups.
- AL-106 Health checks, métricas, logs y alertas.

### M2 — DJI Pilot 2

- AL-201 Página H5 y JSBridge oficial.
- AL-202 Licencia, workspace y bootstrap MQTT.
- AL-203 Registro de topología y seriales.
- AL-204 Captura de mensajes originales y fixtures.
- AL-205 Reconexión, rotación de credenciales y revocación.

### M3 — Vuelos y seguimiento

- AL-301 Máquina de estados de vuelo.
- AL-302 Normalización de telemetría y eventos.
- AL-303 Evidencia, logs originales y SHA-256.
- AL-304 Dashboard e inventario online.
- AL-305 Lista y detalle de sesiones de vuelo.
- AL-306 Bandeja de excepciones.

### M4 — Piloto

- AL-401 Seguridad, carga, desconexión y recuperación.
- AL-402 Cinco vuelos en modo sombra.
- AL-403 Diez vuelos automáticos.
- AL-404 Soak test de 24 horas.
- AL-405 Restauración desde respaldo.
- AL-406 Runbooks y aprobación operativa.

## Criterios de aceptación del piloto

- Control y aeronave aparecen online con seriales correctos.
- Un vuelo terminado queda disponible en un máximo de cinco minutos.
- Reintentos y mensajes duplicados no crean vuelos duplicados.
- Las sesiones incompletas quedan en excepciones.
- El mensaje original y la evidencia descargada conservan un hash verificable.
- No hay acceso MQTT anónimo ni acceso cruzado entre dispositivos.
- Se ejecuta y verifica una restauración completa.
