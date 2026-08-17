# Seguimiento GitHub

## Repositorio

- Remoto: `DovaCrii/AeroLink`.
- Visibilidad: **pública**, a conciencia (decidido el 2026-08-17). El documento decía
  "privada" y el repositorio nació público el 2026-08-06; se corrige el documento, no
  el repositorio.

### Qué no se escribe en un repositorio público

La consecuencia de esa decisión es una regla, porque sin ella la documentación
operacional publica el mapa de la infraestructura:

- **Nada de FQDN resolubles, IP públicas o de tailnet, ni nombres de usuario de la
  VM.** Van como variables (`$AL_HOST`, `$AL_TS_IP`, `$AL_USER`) o como marcadores
  (`<vm>.<tailnet>.ts.net`); los valores reales viven en la VM y en el canal interno.
  El apodo interno del host (`p340`) sí se usa: no resuelve a nada.
- **Ningún secreto, ni de ejemplo con forma real.** `.env` está fuera de Git
  (`.gitignore:10`) y los secretos se generan en la máquina.
- **Ninguna captura ni payload DJI real**, como ya exige `AGENTS.md`.

Saneado el 2026-08-17 en los ADR, el plan, la arquitectura y los runbooks. **El
historial de git conserva los valores anteriores**: rotar el FQDN o la IP no es
proporcional al riesgo —no son secretos, son ubicación— pero conviene saber que
borrarlos del árbol no los borra del historial.
- Rama protegida: `main`.
- Ramas de trabajo: `codex/<area>-<descripcion>`.
- Toda funcionalidad entra mediante pull request con CI verde.

## Project

Nombre: `AeroLink — Implementación`

Estados: `Backlog`, `Ready`, `In progress`, `In review`, `Blocked`, `Done`.

Campos: `Fase`, `Prioridad`, `Área`, `Milestone`, `Responsable`,
`Criterio de aceptación` y `Dependencias`.

## Labels

`type:epic`, `type:feature`, `type:security`, `type:test`, `type:docs`,
`area:infrastructure`, `area:dji`, `area:backend`, `area:mqtt`, `area:ui`,
`area:operations`, `priority:P0`, `priority:P1`, `priority:P2`, `priority:P3`,
`blocked:external`, `needs-decision`, `pilot`.

## Regla de entrada

Los milestones e issues de `docs/MASTER_PLAN.md` deben existir en GitHub antes
de comenzar AL-101. Cada issue debe contener alcance, dependencias y criterio
de aceptación; el cierre requiere PR enlazado y CI verde.

