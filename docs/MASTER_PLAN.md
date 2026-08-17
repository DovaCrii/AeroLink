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
- AL-003 Validación de ingreso público p340, DNS, TLS, HTTPS y MQTT. **Medido el
  2026-08-10: no hay ingreso TCP a la IP pública, ni 443 ni 8883** (ver *Estado
  del gate de red* al final de este plan).
- AL-004 Registro de aplicación y licencia DJI Cloud API. **Las tres credenciales ya
  existen** (preflight `--scope license` en verde el 2026-08-13); esto no está esperando
  a DJI. Se cierra cuando la Prueba 2 confirme que DJI las acepta para el dominio que se
  publique — ver [ruta de prueba](operations/RUTA_DE_PRUEBA.md).
- AL-005 ADR de arquitectura, amenazas, retención y respaldos.

### M1 — Plataforma

- AL-101 Scaffold FastAPI, worker, Docker Compose y CI.
- AL-102 PostgreSQL, migraciones y modelo de datos.
- AL-103 Microsoft Entra ID, roles y auditoría.
- AL-104 Broker MQTTS con TLS, autenticación, rotación y ACL. Dividido por el
  ADR-0004: (a) el cliente saliente que consume el relay —fusionado en el PR #37— y
  (b) la configuración del relay externo, que no se puede terminar sin proveedor
  elegido. Ya no es "EMQX en p340": ese servicio queda para desarrollo local.
- AL-105 Almacenamiento de evidencias, hashes, retención y backups.
- AL-106 Health checks, métricas, logs y alertas.
- AL-107 API de inventario de dispositivos para AeroControl (ADR-0002 fase 2, ADR-0003). Expone **sólo lo que AeroLink masterea** —baterías, payloads y topología de control—, nunca aeronaves: el padrón es de AeroControl (AL-R4), y pedirlo aquí responde 403. No depende del gate de red de AL-R1, que bloquea MQTTS y no HTTPS, así que es entregable antes que el resto de M1.

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
| **AL-R6** ✅ | **Resuelta el 2026-08-13: Entra ID en AeroLink, AeroControl sin cambios** ([ADR-0005](adr/0005-identidad-de-personas-con-entra-id.md)). Se asume la fricción de dos logins a conciencia; no se construye modo local de respaldo. | Entra ID en AeroLink y cuentas Django en AeroControl son dos logins para las mismas ~8 personas. Las opciones son: AeroControl migra a Entra ID, AeroLink acepta un modo local, o se asume la fricción a conciencia. Cualquiera sirve; decidirlo después de construir AL-103 no. |
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

---

## Estado del gate de red (AL-003 / AL-R1) — 2026-08-10

`AL-R1` advirtió que el gate de red era el camino crítico y que era *probable*
que fallara. Se midió y falló. Desde fuera de la red Tailscale, contra la IP
pública de p340 (`200.54.29.98`):

| Puerto | ICMP | TCP |
|---|---|---|
| 443 (HTTPS) | responde | cerrado/filtrado |
| 8883 (MQTTS) | responde | cerrado/filtrado |

Ningún puerto TCP entrante está abierto, ni siquiera el 443 que AeroControl usa a
diario: ese tráfico no entra por la IP pública, entra por el túnel saliente de
Tailscale Funnel, que sirve HTTPS y nada más. **Hoy no existe camino para que un
control DJI alcance un broker en p340.**

**Dirección adoptada:** el broker de producción vive en un **relay externo** con
IP pública propia; p340 lo consume con una conexión saliente. Opciones evaluadas,
consecuencias y lo que queda pendiente están en el
[ADR-0004](adr/0004-broker-mqtt-en-relay-externo.md). `AL-R1` **no se cierra**
hasta elegir el proveedor del relay, su DNS con certificado válido y su ACL.

Efecto en el orden del plan:

- **M2 completo sigue bloqueado** por esto, no solo `AL-104`.
- Lo que entra por HTTPS no está afectado: `AL-102`, `AL-105`, `AL-106` y
  `AL-107` son entregables antes de resolver el relay.
- Si `AL-002`/`AL-204` confirman que el firmware de la flota admite MQTT sobre
  WSS, el relay se vuelve innecesario. Vale la pena verificarlo antes de pagar
  por infraestructura: la [ruta de prueba](operations/RUTA_DE_PRUEBA.md) la deja
  como Prueba 3, dentro de una sesión con un control que ya se necesita para las
  Pruebas 1 y 2.

## Estado de ejecución — 2026-08-13

Todo el trabajo escrito está **en `main`**; ya no hay ramas parqueadas.

| Qué | Dónde | Estado |
|---|---|---|
| Esquema de datos, FastAPI con `/health`/`/ready`/`/metrics`, diagnóstico H5 y preflight de licencia, docker-compose de desarrollo | PR #29, #31, #32, #33 | Fusionado; `AL-101` y `AL-102` cerrados |
| `AL-107` — inventario de dispositivos para AeroControl (token de servicio, auditoría, 51 pruebas) | PR #35 | Fusionado; falta desplegarlo en p340 |
| `AL-104` (a) — cliente MQTT saliente hacia el relay, persiste `RawMessage` con SHA-256 | PR #37 | Fusionado; no puede correr hasta que exista el relay |
| `AL-104` (a) endurecido — sesión persistente y acuse manual: QoS 1 significa algo al reiniciar | PR #38 | Fusionado |
| `AL-106` — métricas de ingesta que sobreviven al reinicio del worker, y sondas que fallan rápido | PR #39 | Fusionado; faltan las reglas de alerta y su destinatario |
| `AL-105` — evidencia con hash verificable, direccionada por contenido, retención como consulta | PR #40 | Fusionado; sin ruta HTTP hasta `AL-103` |
| `AL-R6` resuelta — identidad con Entra ID | PR #41 | [ADR-0005](adr/0005-identidad-de-personas-con-entra-id.md) |
| `AL-203` — `DeviceTopology`, su migración y su escritor, por serial y sin calce difuso | PR #42 | Fusionado; falta que `AL-302` lo llame con datos reales |
| Runbook de despliegue y `root_path` para convivir con AeroControl en el mismo 443 | PR #43, #44, #45 | Fusionado; ejecutado en p340 |
| `Enum` guardaba el nombre del miembro y Postgres esperaba el valor | PR #46 | Fusionado; corrige un 500 en producción |

## Desplegado en p340 — 2026-08-14

AeroLink corre en la VM, junto a AeroControl y sin compartir nada más que la
entrada HTTPS. Lo verificado en el despliegue:

- Migraciones aplicadas sobre **Postgres** hasta `20260813_0002`; `/health` y
  `/ready` responden.
- `https://p340.tailccd107.ts.net/aerolink` sirve la H5 **sin credenciales**
  (`pilot2-connectivity`) y `/` sigue sirviendo AeroControl intacto.
- El **preflight de licencia quedó sin bloqueadores**: las cuatro comprobaciones en
  `pass`, incluida `https_endpoint`. Lo único que falta de `AL-004` es que DJI acepte
  la licencia, y eso sólo lo dice el control.
- El `worker` está detenido a propósito: sin relay no tiene a qué conectarse.

Lo que el despliegue enseñó, y que ningún documento decía:

- **Publicar la API completa por Funnel dejaba `/metrics`, `/docs` y
  `/openapi.json` en internet** — medido, los tres respondían 200. Corregido: la ruta
  pública sirve sólo la superficie H5 aislada, y la API se lee por loopback.
- **La página de diagnóstico incrusta las credenciales DJI** en su HTML, porque la
  verificación de licencia de DJI es client-side. Se publica sólo mientras dura la
  Prueba 2; el resto del tiempo va la superficie sin credenciales.
- **La suite pasaba en verde sobre un defecto que Postgres rechaza.** `sa.Enum`
  degradado a VARCHAR en sqlite aceptaba el nombre del miembro. Correr las pruebas
  contra Postgres en CI es la mejora que habría evitado el 500.

## Lo que queda

- **Una dependencia externa que conviene iniciar ya**: registrar la aplicación en
  el tenant de Entra ID ([ADR-0005](adr/0005-identidad-de-personas-con-entra-id.md)).
  Sin eso `AL-103` no termina, y sin `AL-103` la evidencia de `AL-105` no tiene
  ruta de descarga. Es la misma lección de `AL-R2`.
- **Una decisión que puede quedar sin tomarse**: `AL-R1`, el proveedor del relay.
  Las Pruebas 3 y 3b de la [ruta de prueba](operations/RUTA_DE_PRUEBA.md) dicen si
  Pilot 2 acepta WSS o si Funnel puede reenviar TCP en 8443; si alguna funciona, no
  hay nada que comprar.
- **Una sesión de operación**: `AL-002`, un control y ~90 minutos habilitan las
  Pruebas 1, 2, 3 y 3b de una vez.
- **Respaldo de lo desplegado**: los volúmenes de Postgres y MinIO en p340 no tienen
  respaldo propio verificado. Parte de `AL-105`, y antes de que entre evidencia real.
- **Postgres en CI**: la única forma de que la suite vea las divergencias que hoy
  sólo están documentadas en `tests/conftest.py`.
