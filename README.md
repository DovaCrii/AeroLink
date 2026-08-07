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

**Qué no hace (a propósito):** no envía comandos ni controla la aeronave, no
genera ni publica misiones DJI, y **no se integra con AeroControl todavía** —
es un sistema separado por diseño (ver [ADR-0001](docs/adr/0001-standalone-boundary.md)).

## Documentación y seguimiento

- [Plan maestro](docs/MASTER_PLAN.md) — milestones M0–M4 e issues por bloque.
- [Arquitectura](docs/ARCHITECTURE.md) — servicios, datos propios y el gate de red.
- [Seguimiento GitHub](docs/GITHUB_TRACKING.md) — convención de ramas, labels y project.
- [ADR-0001](docs/adr/0001-standalone-boundary.md) — por qué AeroLink es independiente de AeroControl.

## Estado actual

**M0 en curso** — validando viabilidad antes de construir sobre supuestos que
después haya que deshacer. Ya hay una base técnica real (esquema de datos
completo, FastAPI con `/health`/`/ready`/`/metrics`, verificación de
conectividad y de licencia DJI sin credenciales en tiempo de ejecución,
docker-compose con Postgres/EMQX/MinIO), pero **nada de eso está fusionado a
`main` todavía** — vive en pull requests abiertos, sin revisar. El detalle
exacto (cuáles, en qué quedaron y qué falta) está en el plan maestro.

El riesgo más alto identificado: **`p340` se expone por Tailscale Funnel, que
sirve HTTPS pero no MQTTS (8883)** — sin resolver eso, M1 no puede avanzar.
Ver el detalle y las alternativas en `docs/ARCHITECTURE.md` → *Gate de red*.

## Licencia

Uso interno. Sin licencia pública definida todavía.
