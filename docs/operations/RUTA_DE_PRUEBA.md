# Ruta de prueba: qué se puede probar hoy, y con qué información

Este documento responde una sola pregunta: **cuándo se puede poner esto frente a un
control DJI real y ver si funciona.** El runbook
[PILOT2_CONNECTION_RUNBOOK.md](PILOT2_CONNECTION_RUNBOOK.md) dice *cómo* se ejecuta
la prueba; esto dice *cuál* se puede ejecutar ya, cuál no, y qué información entrega
cada una.

## El hallazgo que cambia el orden (2026-08-13)

`AL-004` (registro de aplicación y licencia DJI Cloud API) está marcado
`blocked:external` en el tablero, como si el proyecto estuviera esperando a DJI.
**No lo está.** El preflight offline, corrido hoy:

```powershell
uv run python aerolink_preflight.py --scope license
```

devuelve `pass` en `dji_app_id`, `dji_app_key` y `dji_app_license` —las tres
credenciales existen en el `.env` local, fuera de Git— y deja **un solo bloqueador**
en ese alcance:

```
https_endpoint  blocker  APP_BASE_URL must be a non-local HTTPS URL for Pilot 2.
```

Hoy `APP_BASE_URL` es `http://127.0.0.1:8081`. Es decir: lo que separa a AeroLink de
su primera prueba real **no es DJI, ni el relay, ni M1** — es publicar la página H5 en
una URL HTTPS pública. Y eso es exactamente lo único que la red de p340 ya sabe hacer:
Tailscale Funnel sirve HTTPS. El gate del ADR-0004 bloquea MQTTS 8883, no esto.

Que las credenciales *existan* no prueba que DJI las acepte para el dominio que se
publique. Eso lo dice la Prueba 2, y es justamente la información que se busca.

## Escalera de pruebas

| # | Prueba | Requiere | Qué información entrega | Costo |
|---|---|---|---|---|
| 0 | Inventario de baterías punta a punta | `AL-107` desplegado en p340 (el código ya está en `main`), token de servicio | Si el contrato con AeroControl funciona sobre infraestructura real | Cero infra nueva |
| 1 | H5 + JSBridge, sin licencia | Un control en mano, una URL HTTPS pública temporal | Si Pilot 2 carga una página nuestra y expone JSBridge | Cero |
| 2 | H5 + **licencia verificada** | Prueba 1 + `APP_BASE_URL` público | **Si la licencia DJI sirve.** Es el gate real de M2 | Cero |
| 3 | **Sonda WSS** | Misma sesión de la Prueba 2 | Si el relay del ADR-0004 es necesario o se puede evitar | Minutos |
| 3b | **Sonda de Funnel TCP en 8443** | Misma sesión, más un broker local | Lo mismo por otra vía: Funnel también reenvía TCP | Minutos |
| 4 | Control online en el broker | Relay elegido **o** WSS confirmado, credenciales por dispositivo, ACL | Primer `RawMessage` real con hash | Relay, si hace falta |
| 5 | Vuelo en modo sombra (`AL-402`) | M3 | Si una sesión de vuelo se reconstruye bien | Tiempo de operación |

### Prueba 0 — sin hardware DJI, se puede hoy

Ya se verificó local el 2026-08-12: AeroControl sincronizó 2 baterías contra el
endpoint real de AeroLink y enlazó una a `RPA-2002` por número de serie. Lo que falta
es repetirlo contra p340 desplegado. Dos precondiciones que no son de AeroLink:

- desplegar `AL-107` en p340 — el código ya está en `main` (PR #35) y el
  procedimiento en el [runbook de despliegue](DEPLOY_P340.md);
- correr `manage.py audit_serial_case` en p340 **antes** del primer sync real —
  cambiar `save()` no reescribe filas ya guardadas.

### Pruebas 1 a 3 — una sola sesión con un control

Las tres se hacen seguidas, con un control y un operador, sin despegar y sin gastar en
infraestructura:

1. **Prueba 1** usa el servicio `pilot2-connectivity` (escucha en `127.0.0.1:8092` y
   **no lee `.env`**): se publica por Funnel y sólo demuestra que Pilot 2 alcanza una
   página H5 y detecta JSBridge. No toca licencia ni credenciales. Es la superficie
   que debe quedar publicada **por defecto** entre pruebas.
2. **Prueba 2** cambia la ruta pública al servicio `pilot2-diagnostic` (8090) y abre esa
   página desde Pilot 2. Resultado esperado: **"JSBridge disponible"** y **"Licencia DJI
   verificada"**. En un navegador normal, JSBridge debe aparecer como no disponible —
   ese contraste es parte del resultado.

   **Se publica sólo mientras dure la prueba y se retira al terminar.** La verificación
   de licencia de DJI ocurre en el cliente, así que esa página lleva `appId`, `appKey` y
   `license` en su propio HTML: publicada, las expone a cualquiera que haga `curl`. Es
   el diseño de DJI, no un defecto nuestro, y por eso existe la superficie sin
   credenciales de la Prueba 1 para el resto del tiempo.
3. **Prueba 3** es la que puede ahorrar el relay: con la sesión ya montada, intentar que
   el Cloud Module apunte a un host **`wss://`** servido por Funnel en vez de a
   `mqtts://…:8883`. Si Pilot 2 lo acepta, el relay externo del
   [ADR-0004](../adr/0004-broker-mqtt-en-relay-externo.md) **no se necesita** y M2 se
   desbloquea sin contratar nada. Si no lo acepta, el relay se contrata con evidencia en
   vez de con una suposición.

4. **Prueba 3b** es la misma pregunta por otra vía, y apareció después de escribir el
   ADR-0004: Funnel **también reenvía TCP** (`--tcp`, `--tls-terminated-tcp`) en 443,
   8443 y 10000. Lo que AL-003 midió cerrado fue el TCP directo contra la IP pública
   del sitio, y Funnel no publica por ahí. Con
   `sudo tailscale funnel --bg --tls-terminated-tcp 8443` hacia un broker local,
   Tailscale termina el TLS con su certificado válido y entrega TCP plano en
   loopback: el broker no necesita certificado propio y Pilot 2 conectaría a
   `<vm>.<tailnet>.ts.net:8443`. Hay que medir dos cosas antes de creerle —que DJI
   acepte un puerto distinto de 8883, y que Funnel tolere una sesión MQTT de horas,
   para lo que no está diseñado—. Si aguanta, **no hay relay que comprar**.

Ninguna de estas pruebas habilita comandos, despegue ni misiones. Se detienen si falla
el certificado, la licencia o cualquier ACL.

## Lo que hay que conseguir, en este orden

1. **Un control y 90 minutos de operación** — es el insumo más escaso y el que más
   información destraba (Pruebas 1, 2 y 3 de una vez). La combinación tiene que ser una
   de las dos que el runbook admite: Mavic 3E con RC Pro Enterprise, o Matrice 4E/4T con
   RC Plus 2 (`AL-002`).
2. **Un FQDN HTTPS público para AeroLink.** Punto a verificar antes de la sesión: cómo
   conviven AeroControl y AeroLink en el mismo nodo de Funnel —hostname o puerto
   distinto— y si Pilot 2 acepta un puerto no estándar en la URL del H5. Si no lo
   acepta, hay que separar hostnames.
3. **Sólo si la Prueba 3 falla:** proveedor del relay, su DNS con certificado válido y su
   ACL. Es decir: la decisión que hoy bloquea `AL-R1` puede quedar sin comprarse.

## Higiene mientras se prueba

- La página de diagnóstico se publica **temporalmente** y se retira al terminar; toma las
  credenciales del entorno y no las persiste ni las registra, pero una URL pública que
  dispara verificación de licencia no debe quedar viva sin necesidad.
- Las credenciales DJI viven sólo en el `.env` de la máquina (verificado: no está en Git,
  `.gitignore:10`). No entran a issues, capturas ni chat.
- Evidencia mínima de aceptación de cada prueba: la lista está en el runbook, y es
  anonimizada por diseño.
