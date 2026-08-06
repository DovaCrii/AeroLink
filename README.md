# AeroLink

Gateway operativo independiente para conectar DJI Pilot 2 con una plataforma
corporativa de seguimiento de vuelos, telemetría y evidencia técnica.

## Alcance actual

AeroLink se desarrolla como aplicación independiente. La integración con
AeroControl queda fuera de este repositorio y se planificará posteriormente en
`DovaCrii/AeroControl`.

La primera versión se limita a:

- conexión oficial DJI Cloud API desde DJI Pilot 2;
- inventario de controles, aeronaves, payloads y baterías;
- recepción y conservación de telemetría, eventos y logs;
- detección de sesiones de vuelo y seguimiento operacional;
- evidencia con hash SHA-256;
- autenticación individual mediante Microsoft Entra ID;
- dashboard, detalle de vuelos y bandeja de excepciones.

No incluye comandos remotos, control de vuelo ni publicación automática de
misiones.

## Documentación y seguimiento

- [Plan maestro](docs/MASTER_PLAN.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Seguimiento GitHub](docs/GITHUB_TRACKING.md)
- [ADR de separación con AeroControl](docs/adr/0001-standalone-boundary.md)

## Estado

Sondas operativas iniciales:

- `GET /health` confirma que el proceso API responde.
- `GET /ready` confirma que PostgreSQL está disponible antes de aceptar trabajo
  operativo.

Fase M0: preparación del repositorio, inventario de hardware y validación de
conectividad pública para HTTPS/MQTTS.
