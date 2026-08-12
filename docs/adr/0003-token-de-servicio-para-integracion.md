# ADR-0003: Token de servicio para la integración con AeroControl

## Estado

Propuesto — 2026-08-12. Complementa el ADR-0002; no revierte el ADR-0001.

## Contexto

El ADR-0002 fijó el contrato de coexistencia y asignó a AeroLink el dominio de
**baterías, payloads y topología de control**, que AeroControl refleja para su
evidencia ISO 7.1.3. AeroControl ya implementó y probó el lado consumidor
(`sync_batteries`, 17 pruebas) y publicó el contrato que espera. Falta el
productor: el endpoint `AL-107`.

Ese endpoint choca con una regla propia de este repo:

> `AGENTS.md`: *"Toda API nueva requiere autenticación, autorización, auditoría y
> pruebas."*

Y hoy **este repositorio no tiene autenticación de ningún tipo**: cero usos de
`Depends()`, `get_db()` definido y nunca importado, `AuditEvent` modelado y sin
un solo escritor. Las cinco rutas existentes son públicas a propósito
(`/health`, `/ready`, `/metrics`, `/pilot2/diagnostic`, `/api/v1`).

La autenticación "de verdad" es `AL-103` (Microsoft Entra ID, roles y auditoría),
y está **bloqueada por una decisión abierta**: `AL-R6` dice que hay que decidir
Entra ID vs cuentas Django *antes* de construirla. Esperar a esa decisión
bloquearía indefinidamente una integración cuyo consumidor ya está terminado.

## Decisión

Se introduce un **token de servicio** para autenticar al único consumidor
máquina (AeroControl) en el único endpoint de lectura del contrato.

- Cabecera `Authorization: Token <valor>` — la forma que el consumidor ya envía.
- Comparación en tiempo constante, nunca registrada en logs.
- Configurado por entorno (`AEROLINK_SERVICE_TOKEN`), con el workspace al que
  da acceso (`AEROLINK_SERVICE_TOKEN_WORKSPACE`).
- **Falla cerrado**: sin token configurado el endpoint responde `503`, no `401`
  ni una lista vacía.

### Por qué esto no prejuzga `AL-R6`

`AL-R6` es una pregunta sobre **identidad humana**: SSO, roles, MFA, ciclo de
sesión para ~8 personas. Este credencial autentica **una máquina, en loopback,
sobre un endpoint de sólo lectura**. Bajo cualquiera de las dos respuestas de
`AL-R6`, un consumidor máquina sigue necesitando un credencial de servicio —
Entra lo daría como *client credentials*, que es la misma forma con más ceremonia
y una dependencia externa que este repo todavía no tiene.

### Cláusula de caducidad (la parte que importa)

El riesgo no es el token: es que **crezca**. Este token:

- **Nunca** se acepta en un endpoint de escritura. Sólo lectura, para siempre.
- **Nunca** autentica a una persona ni a un navegador: sin cookie, sin formulario
  de login, sin proteger `/docs` con él.
- **Nunca** crece a un segundo token ni a roles. *Un segundo consumidor, o un
  segundo nivel de permiso, es la señal de implementar `AL-103`* — no de agregar
  `service_token_2`.
- **Nunca** se reutiliza como credencial MQTT (`AL-104`), licencia DJI ni
  `app_secret_key`.
- **Nunca** es la base sobre la que `AL-103` construye. Vive en su propio módulo
  (`auth.py`) con una sola dependencia exportada, justamente para que `AL-103` lo
  **borre** en vez de extenderlo.

**Se elimina cuando `AL-103` aterrice.**

### Limitación que se declara en vez de disimular

Ambos servicios comparten VM, así que el token en `.env` vale lo que valga la
separación de usuarios del sistema de archivos entre los dos procesos. Es un
control de **segmentación, no de secreto**: detiene a un llamador equivocado o
de terceros, no a un co-inquilino comprometido. Para loopback es suficiente y
honesto decirlo.

Tampoco hay *throttling*: este repo no tiene una primitiva para eso y agregarla
significa una dependencia nueva. Aceptable porque la superficie es loopback con
un consumidor programado. **Disparador registrado: si este endpoint alguna vez se
publica por Tailscale Funnel, el throttling pasa a ser obligatorio antes.**

## Consecuencias

**A favor**

- Desbloquea el reflejo de baterías (ISO 7.1.3 de AeroControl) sin esperar a M2,
  M3 ni a la decisión `AL-R6`.
- Introduce en el repo el **primer camino de escritura de `AuditEvent`** y la
  **primera fixture de base de datos** en pruebas — infraestructura que `AL-103`
  y todo endpoint posterior reutilizan.
- El `kind` expuesto se restringe por lista blanca a lo que AeroLink **sí**
  masterea (batería, payload, controlador). `kind=aircraft` responde `403`
  citando `AL-R4`: convierte *"no duplicar el padrón"* de párrafo en una
  aserción que una prueba verifica.

**En contra**

- Un mecanismo de autenticación que hay que borrar después. Mitigado por la
  cláusula de caducidad y por vivir aislado en un módulo.
- Auditar lecturas convierte un camino de lectura en uno de escritura, y falla
  cerrado: si no se puede registrar el acceso, no se entrega el inventario. Es
  deliberado —entregar datos que no se pudieron registrar es justo lo que ISO no
  quiere— y el costo es que un disco lleno detiene la sincronización.

**Hallazgo cruzado que hay que resolver del lado de AeroControl**

El ADR-0002 §2 manda normalizar el serial a mayúsculas. AeroControl sólo
implementaba la parte de los espacios; corregido allí el 2026-08-12
(`normalize_serial`, migración `registry/0032` y `manage.py audit_serial_case`).
**Antes del primer sync con datos reales hay que correr esa auditoría en
producción**: cambiar el guardado no reescribe filas ya almacenadas, y un serial
con minúsculas dejaría de calzar en silencio.

## Alternativas descartadas

- **Esperar a `AL-103`.** Bloquea la integración detrás de una decisión de
  identidad humana que no tiene fecha y que no es necesaria para una máquina.
- **Dejar el endpoint público** porque es loopback. Contradice `AGENTS.md` de
  frente, y "está en loopback" es una propiedad del despliegue de hoy, no del
  código: una línea de configuración de Funnel la borra.
- **Entra client credentials ahora.** Es lo correcto a futuro, pero exige
  `msal`/JWT como dependencias y un registro de aplicación, para un consumidor
  que corre a un metro de distancia sobre la interfaz de loopback.

---

*Relacionado:* [ADR-0002](0002-contrato-coexistencia-aerocontrol.md);
`AeroControl/docs/dev/plan-integracion-aerolink.md` (el plan separado que
`AGENTS.md` exige); `AL-107` en [MASTER_PLAN](../MASTER_PLAN.md).
