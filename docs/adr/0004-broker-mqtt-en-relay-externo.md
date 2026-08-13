# ADR-0004: El broker MQTT vive en un relay externo, no en p340

## Estado

Propuesto — 2026-08-13. Resuelve la dirección de `AL-R1`; no revierte el
ADR-0001. Queda pendiente elegir el proveedor concreto del relay.

## Contexto

El plan maestro dejó `AL-003` (ingreso público de p340) como gate de M1, y la
revisión externa lo elevó a bloqueante (`AL-R1`) porque era *probable* que
fallara. Ya no es una probabilidad: el 2026-08-10 se midió desde fuera de la red
Tailscale contra la IP pública de p340 (`200.54.29.98`).

| Puerto | ICMP | TCP |
|---|---|---|
| 443 (HTTPS) | responde | cerrado/filtrado |
| 8883 (MQTTS) | responde | cerrado/filtrado |

Ningún puerto TCP entrante está abierto en esa IP —**ni siquiera el 443 que usa
AeroControl a diario**, porque ese tráfico no entra por la IP pública: Tailscale
Funnel abre un túnel *saliente* hacia el relay de Tailscale, que termina el TLS
y reenvía por dentro. Ese mecanismo sirve HTTPS y solo HTTPS; no expone puertos
TCP arbitrarios como el 8883.

La consecuencia es directa: **hoy no existe ningún camino para que un control DJI
alcance un broker alojado en p340.** El supuesto del ADR-0001 y de
`ARCHITECTURE.md` —"todos los servicios se despliegan en p340"— es falso para el
broker, y solo para el broker.

## Opciones

1. **NAT / IP pública en el sitio de p340.** Abrir 8883 (y 443) en el router
   hacia la VM. Es la opción más simple de arquitectura y la que menos cambia el
   plan, pero depende de control administrativo sobre el router y el ISP, que
   hoy no está confirmado, y expone la VM operacional a internet — la misma VM
   que corre AeroControl.
2. **Relay MQTT externo con IP pública propia.** El broker deja de vivir en p340:
   corre en un host con ingreso público real, DJI Pilot 2 publica ahí, y AeroLink
   lo consume con una conexión **saliente** desde p340 — la única que ya se sabe
   que funciona.
3. **MQTT sobre WSS por Funnel.** Aprovecharía el HTTPS que ya entra, sin
   infraestructura nueva, pero depende de que el firmware DJI de la flota admita
   MQTT sobre WebSocket seguro. No está verificado (`AL-002`, `AL-204`) y no se
   puede asumir por modelo de aeronave.

## Decisión

Se adopta la **opción 2**: el broker de producción vive en un relay externo y
AeroLink es su *cliente*, nunca su servidor.

- `MQTT_PUBLIC_HOST` / `MQTT_TLS_PORT` pasan a nombrar la dirección **del relay**,
  no la de p340.
- El servicio `emqx` de `docker-compose.yml` queda marcado como **solo
  desarrollo**; no es el broker que verá DJI.
- El worker se conecta hacia afuera con TLS contra el almacén de CA del sistema
  (el relay lleva certificado público real), se suscribe y persiste cada mensaje
  **sin interpretarlo** en `RawMessage`, con su SHA-256. Interpretar el formato
  de DJI es `AL-302`, después de que `AL-204` capture fixtures reales; adivinar
  la forma del payload ahora sería peor que no parsearlo.
- Dos identidades MQTT distintas: la que DJI Pilot 2 usa para **publicar** y la
  del worker para **suscribirse** (`MQTT_WORKER_USERNAME`/`_PASSWORD`).

La opción 3 no queda descartada, queda **postergada**: si `AL-002`/`AL-204`
confirman WSS en el firmware de la flota, es más barata que un relay y merece
reevaluarse antes del piloto. La opción 1 sigue siendo válida si aparece control
sobre el router; entonces el relay se vuelve innecesario, no incorrecto.

## Consecuencias

- **La telemetría transita infraestructura de terceros.** Es un cambio real de
  superficie de exposición respecto del ADR-0001, que asumía todo dentro de p340.
  Hay que tratarlo en el modelo de amenazas (`AL-005`) antes del piloto: qué ve
  el relay, qué se retiene ahí, y por cuánto tiempo. La evidencia con hash y la
  retención de 5 años (`AL-105`) siguen viviendo en p340 — el relay es tránsito,
  no archivo.
- **El relay es un punto único de falla nuevo.** Su caída no debe perder
  mensajes: suscripción con QoS 1 y sesión persistente, y `AL-205`
  (reconexión/rotación) pasa a cubrir también este tramo.
- **`AL-104` se divide.** Lo que era "EMQX con TLS, autenticación, rotación y
  ACL" en p340 ahora son dos cosas: el cliente saliente (hecho, en la rama
  `codex/relay-worker`) y la configuración del relay —ACL por dispositivo, sin
  usuarios anónimos, credenciales rotables— que no se puede terminar sin
  proveedor elegido.
- **Costo recurrente** de un host externo, que antes no estaba en el plan.
- El resto de M1 (`AL-102`, `AL-105`, `AL-106`, `AL-107`) **no depende de esto**:
  entra por HTTPS o no entra por la red en absoluto.

## Pendiente antes de cerrar AL-R1

1. Elegir el proveedor y el nombre DNS del relay, con certificado público válido.
2. Definir su ACL y el esquema de credenciales por control.
3. Confirmar la retención en el relay (idealmente cero: tránsito puro).
