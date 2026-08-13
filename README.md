# AeroLink

**Gateway independiente que conecta DJI Pilot 2 con un registro propio de
vuelos, telemetría y evidencia técnica.**

## Qué es

AeroLink recibe la información que DJI Pilot 2 expone durante un vuelo
—identidad del control y la aeronave, telemetría, eventos— y la convierte en
un registro operativo: sesiones de vuelo reconstruidas, evidencia con hash
verificable y un inventario de equipos en línea. Reemplaza la dependencia de
capturas de pantalla y planillas de terreno para dejar constancia de qué se
voló, con qué equipo y cuándo.

**Qué no hace (a propósito):** no envía comandos ni controla la aeronave, y no
genera ni publica misiones DJI. Sigue siendo un sistema separado de AeroControl
por diseño (ver [ADR-0001](docs/adr/0001-standalone-boundary.md)): despliegues
independientes, sin base de datos compartida y sin que ninguno escriba en el
dominio del otro.

**Lo único que comparte con AeroControl** es un contrato HTTP versionado y de
sólo lectura: `GET /api/v1/devices/?kind=battery` expone el inventario que
AeroLink masterea —baterías, payloads, topología de control— para que AeroControl
lo refleje como evidencia ISO 7.1.3. Las aeronaves **no** se exponen: ese padrón
es de AeroControl y pedirlo aquí responde `403`. Ver
[ADR-0002](docs/adr/0002-contrato-coexistencia-aerocontrol.md) (contrato),
[ADR-0003](docs/adr/0003-token-de-servicio-para-integracion.md) (credencial) y
`AeroControl/docs/dev/plan-integracion-aerolink.md` (el plan conjunto).

Requiere configurar `SERVICE_TOKEN` y `SERVICE_TOKEN_WORKSPACE`; sin ellos el
endpoint responde `503` y no expone nada.

## Documentación y seguimiento

- [Plan maestro](docs/MASTER_PLAN.md) — milestones M0–M4 e issues por bloque.
- [Arquitectura](docs/ARCHITECTURE.md) — servicios, datos propios y el gate de red.
- [Seguimiento GitHub](docs/GITHUB_TRACKING.md) — convención de ramas, labels y project.
- [ADR-0001](docs/adr/0001-standalone-boundary.md) — por qué AeroLink es independiente de AeroControl.
- [ADR-0004](docs/adr/0004-broker-mqtt-en-relay-externo.md) — por qué el broker no vive en p340.
- [Ruta de prueba](docs/operations/RUTA_DE_PRUEBA.md) — qué se puede probar hoy con un control, y qué información entrega cada prueba.

## Estado actual

**M0 en curso, con su gate resuelto en contra.** Todo lo escrito está en `main`:
esquema de datos completo, FastAPI con `/health`/`/ready`/`/metrics`, verificación
de conectividad y de licencia DJI sin credenciales en tiempo de ejecución,
docker-compose de desarrollo con Postgres/EMQX/MinIO, el inventario de dispositivos
para AeroControl (`AL-107`) y el cliente MQTT saliente hacia el relay
(`AL-104` (a)).

El riesgo más alto **se confirmó el 2026-08-10**: medido desde fuera, la IP
pública de `p340` no acepta TCP entrante en 443 ni en 8883. Tailscale Funnel no
abre puertos ahí y sirve HTTPS solamente, así que **ningún control DJI puede
alcanzar un broker alojado en p340**. El camino adoptado es un **relay MQTT
externo** con p340 como cliente saliente —ver
[ADR-0004](docs/adr/0004-broker-mqtt-en-relay-externo.md)— y falta elegir su
proveedor. Mientras eso no se resuelva, M2 sigue bloqueado; lo que entra por
HTTPS no lo está.

Lo que falta ya no es código sin escribir: son decisiones y una sesión de prueba.
El detalle está en el [plan maestro](docs/MASTER_PLAN.md) → *Estado de ejecución*.

**Lo que sí se puede probar ya:** las credenciales DJI existen y el preflight de
licencia está en verde, así que la primera prueba real con un control —H5,
JSBridge y verificación de licencia— **no depende del relay**, sólo de publicar la
página en una URL HTTPS pública, que es justo lo que Funnel ya hace. En la misma
sesión se puede sondear si Pilot 2 acepta MQTT sobre WSS y, si lo acepta, el relay
deja de ser necesario. La escalera completa está en la
[ruta de prueba](docs/operations/RUTA_DE_PRUEBA.md).

## Licencia

Uso interno. Sin licencia pública definida todavía.
