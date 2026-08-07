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

El levantamiento se realiza con la [plantilla de inventario DJI](operations/DJI_FLEET_INVENTORY_TEMPLATE.md),
sin incorporar seriales ni secretos al repositorio.

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

---

## Revisión externa (2026-08-07)

Revisión hecha desde `DovaCrii/AeroControl` al planificar la coexistencia entre
ambos sistemas. El plan de arriba es coherente y su ADR-0001 acierta en separar
los despliegues. Lo que sigue son siete ajustes de **orden y de riesgo**, no de
alcance: ninguno agrega funcionalidad, todos adelantan el momento en que un
problema se descubre.

Contraparte en AeroControl:
[`docs/dev/adr-0002-coexistencia-aerolink.md`](https://github.com/DovaCrii/AeroControl/blob/main/docs/dev/adr-0002-coexistencia-aerolink.md)
y el bloque `X` de su `MASTER_PLAN.md`.

| ID | Ajuste propuesto | Por qué |
|---|---|---|
| **AL-R1** | **Elevar AL-003 (gate de red) a bloqueante explícito con fecha límite, y documentar el plan B antes de gastar en M1.** | Es el camino crítico de todo el proyecto y hoy **es probable que falle**: `p340` se expone por Tailscale Funnel, que sirve HTTPS pero **no** puertos TCP arbitrarios como MQTTS 8883. Las salidas son NAT/IP pública, un relay MQTT externo, o MQTT sobre WSS si el hardware DJI lo admite. Descubrirlo después de levantar EMQX, PostgreSQL y el worker cuesta M1 entero. |
| **AL-R2** | **Mover AL-004 (licencia DJI Cloud API) a M0, en paralelo**, no dentro de M1. | Es una dependencia externa con plazo propio: cuenta de desarrollador y, según el caso, acuerdo comercial. No la controla el equipo y puede bloquear M2 completo. Iniciarla temprano no cuesta nada; iniciarla tarde cuesta el calendario. |
| **AL-R3** | **Definir el contrato de coexistencia ahora, aunque se implemente después.** Fijar el **número de serie del equipo** como llave compartida. | AL-203 ("registro de topología y seriales") es justo donde nace el problema. El ADR-0001 dice que cada sesión conserva "un identificador externo inmutable", pero no dice externo *a qué*. El serial es la única llave que existe en los tres mundos: la reporta DJI, la registra la DGAC, y está embebida en el repositorio documental de la empresa. |
| **AL-R4** | **No duplicar el padrón.** Consumir aeronaves y operadores desde AeroControl (solo lectura) en vez de que `Device` sea fuente de verdad. | AeroControl ya tiene las 16 aeronaves reales con su centro de costo, seguro y documentación DGAC, y ya expone DRF con token y throttling. Sin esto nacen dos inventarios divergentes de los mismos drones y después hay que reconciliarlos con datos acumulados. **Degradación obligatoria:** si el padrón no responde, la sesión se guarda con el serial crudo y se concilia después — nunca se descarta telemetría por no poder resolver la aeronave. |
| **AL-R5** | **Adelantar la restauración desde respaldo (AL-405) de M4 a M1.** | AeroLink promete evidencia con hash y retención de 5 años, y va a la **misma VM cuyo respaldo nunca se ha restaurado** (es la prioridad #1 abierta de AeroControl). Un respaldo no restaurado no es un respaldo. Probarlo cuando hay poco que perder es barato; probarlo en M4 es probarlo con evidencia real adentro. |
| **AL-R6** | **Decidir la identidad antes de M1** (AL-103). | Entra ID en AeroLink y cuentas Django en AeroControl son dos logins para las mismas ~8 personas. Las opciones son: AeroControl migra a Entra ID, AeroLink acepta un modo local, o se asume la fricción a conciencia. Cualquiera sirve; decidirlo después de construir AL-103 no. |
| **AL-R7** | **Aprovechar que PostgreSQL llega a `p340` con AL-102** para reabrir la migración de AeroControl desde SQLite. | En AeroControl esa migración está diferida por costo de infraestructura. Con Postgres ya instalado y respaldado en la misma VM, el costo cambia: un solo motor, un solo procedimiento de respaldo, una sola restauración que ensayar. No es trabajo de AeroLink, pero es una consecuencia de su llegada que conviene aprovechar. |

### Nota sobre los seriales (afecta AL-001 y AL-203)

El inventario de AeroControl se cruzó contra el repositorio documental de la
empresa el 2026-08-07. De 16 aeronaves, **11 calzan exacto** por serial. Las otras
cinco muestran el tipo de suciedad que AL-203 va a encontrar:

- 2 traen un **espacio espurio** a mitad del serial;
- 2 difieren en un carácter — confusión `O`/`0`, y `1581…` vs `1582…`;
- 1 tiene el centro de costo distinto entre las dos fuentes;
- 1 aeronave del padrón (**Wingtra ONE GEN2**) no es DJI y **nunca aparecerá por
  AeroLink** — el contrato no debe asumir que todo el padrón es alcanzable por
  telemetría.

Implicancia para AL-203: **normalizar antes de comparar** (mayúsculas, sin
espacios) y **no hacer calce difuso**. Atribuir un vuelo a la aeronave equivocada
es peor que dejarlo en la bandeja de excepciones, que para eso existe (AL-306).

### Lo que esta revisión **no** propone

No propone fusionar los dos sistemas. La separación es correcta: la ingesta MQTT
es continua y asíncrona, DJI exige ingreso público con credenciales propias, y
una falla de ingesta no debe voltear el sistema que la operación usa a diario.
Tampoco propone base de datos compartida ni acceso cruzado a filesystem — el
ADR-0001 lo prohíbe y está bien así.
