<div align="center">

<img src="assets/aerolink-mark.svg" width="140" height="105" alt="Logo de AeroLink" />

# AeroLink

**Gateway independiente que conecta DJI Pilot 2 con un registro propio de
vuelos, telemetría y evidencia técnica.**

</div>

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

## Qué resuelve

Hoy la constancia de un vuelo depende de que alguien saque una captura de pantalla y
llene una planilla en terreno. Eso falla de tres formas conocidas:

- **La telemetría se pierde.** Lo que el control sabe —posición, altura, eventos,
  estado de las baterías— vive en la app de DJI y no queda en ninguna parte
  consultable después.
- **El conteo de ciclos de batería se lleva a mano** y se desvía de la realidad de
  inmediato, aunque DJI lo reporte de forma nativa. Es evidencia ISO 7.1.3 apoyada en
  memoria humana.
- **Una captura de pantalla no es evidencia verificable.** No hay hash, no hay
  cadena, no hay forma de demostrar que el archivo es el original.

AeroLink toma esas tres cosas en el origen: reconstruye la sesión de vuelo desde los
mensajes del propio equipo, guarda el mensaje original con su **SHA-256** antes de
interpretarlo, y publica el inventario que masterea para que AeroControl lo refleje sin
que nadie lo teclee dos veces.

## Puesta en marcha

Desarrollo local, con Docker:

```bash
cp .env.example .env          # completar los valores; .env nunca va a Git
docker compose up --build --detach api minio
curl -sS http://127.0.0.1:8081/health
```

`postgres` y `migrate` entran como dependencias de `api`; `migrate` corre
`alembic upgrade head` y el resto espera a que termine bien. El `worker` requiere un
relay MQTT al que conectarse y **falla al arrancar sin él**, a propósito.

Pruebas y gate de calidad, sin Docker:

```bash
uv sync --all-groups
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Para la VM compartida con AeroControl, ver el
[runbook de despliegue](docs/operations/DEPLOY_P340.md).

## Documentación y seguimiento

- [Plan maestro](docs/MASTER_PLAN.md) — milestones M0–M4 e issues por bloque.
- [Arquitectura](docs/ARCHITECTURE.md) — servicios, datos propios y el gate de red.
- [Seguimiento GitHub](docs/GITHUB_TRACKING.md) — convención de ramas, labels y project.
- [ADR-0001](docs/adr/0001-standalone-boundary.md) — por qué AeroLink es independiente de AeroControl.
- [ADR-0004](docs/adr/0004-broker-mqtt-en-relay-externo.md) — por qué el broker no vive en p340.
- [ADR-0005](docs/adr/0005-identidad-de-personas-con-entra-id.md) — cómo se autentican las personas.
- [Ruta de prueba](docs/operations/RUTA_DE_PRUEBA.md) — qué se puede probar hoy con un control, y qué información entrega cada prueba.
- [Despliegue en p340](docs/operations/DEPLOY_P340.md) — cómo convive con AeroControl en la misma VM y la misma entrada HTTPS.

## Estado actual

**Desplegado en p340 desde el 2026-08-14**, junto a AeroControl y sin compartir nada
más que la entrada HTTPS: migraciones aplicadas sobre Postgres, `/health` y `/ready`
respondiendo, la H5 pública sirviendo la superficie **sin credenciales**, y el
preflight de licencia **sin bloqueadores**. El `worker` está detenido a propósito:
sin broker no tiene a qué conectarse. Procedimiento y lo que el despliegue enseñó, en
el [runbook](docs/operations/DEPLOY_P340.md).

**M0 sigue en curso, con su gate resuelto en contra.** Todo lo escrito está en `main`:
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
