# ADR-0005: Las personas se autentican con Microsoft Entra ID

## Estado

Aceptada — 2026-08-13. Resuelve `AL-R6`, la decisión que bloqueaba `AL-103`. No
modifica el ADR-0003, que cubre el camino máquina.

## Contexto

`AGENTS.md` exige que toda API nueva tenga autenticación, autorización, auditoría
y pruebas. Hoy AeroLink tiene exactamente una credencial: el **token de servicio**
del ADR-0003, que autentica a un consumidor máquina —AeroControl— en un endpoint
de sólo lectura. Para personas no hay nada.

Eso ya está frenando trabajo concreto: la capa de evidencia de `AL-105` existe,
está probada y **no tiene ruta HTTP**, porque exponer una descarga sin
autenticación violaría la propia guía del repo. Y la evidencia que descargaría
tiene retención de cinco años.

La revisión externa planteó el problema como `AL-R6`: Entra ID en AeroLink y
cuentas Django en AeroControl son dos logins para las mismas ~8 personas.
Las tres salidas eran migrar AeroControl a Entra, aceptar un modo local en
AeroLink, o asumir la fricción a conciencia.

## Decisión

**AeroLink autentica personas con Microsoft Entra ID (OIDC).** AeroControl no
cambia. Se asume la fricción de dos logins para ~8 personas, a conciencia.

- Los roles del plan —`Administrator`, `Operations`, `Pilot`, `Viewer`— se
  resuelven desde el tenant, no desde una tabla local editable a mano.
- `UserIdentity` gana su primer escritor con `AL-103`: `provider="entra"` y el
  `subject` del token como identidad estable.
- El token de servicio del ADR-0003 **sigue existiendo y no se reemplaza**. Son
  dos caminos distintos a propósito: una máquina no tiene MFA ni sesión, y
  meterla por el flujo de personas obligaría a inventarle una.
- **No se construye un modo local de respaldo.** Si el tenant no está disponible,
  la descarga de evidencia simplemente todavía no existe. Un stopgap de
  autenticación que funciona el día del piloto es un stopgap que se queda.

## Alternativas descartadas

- **Modo local en AeroLink.** Desbloqueaba `AL-103` de inmediato y sin depender de
  nadie, y es la razón por la que se descarta: sería un segundo lugar donde crear
  y revocar personas a mano, con evidencia de cinco años detrás, y la experiencia
  del repo con `AL-004` es que lo temporal sobrevive.
- **Migrar AeroControl a Entra ID.** Es lo más limpio a largo plazo y toca la
  autenticación de la aplicación que la operación usa a diario, incluidos sus
  permisos espejo de DGAC. No en paralelo con el piloto de AeroLink; queda como
  decisión propia de ese repositorio, no bloqueada por esta.

## Consecuencias

- **Aparece una dependencia externa con plazo propio**, igual que `AL-004`:
  registrar la aplicación en el tenant y emitir su secreto requiere
  administrador. `AL-103` no puede terminarse sin eso, y conviene iniciarlo ya —
  la lección de `AL-R2` fue exactamente ésta.
- **Sin tenant no hay endpoint de descarga.** La capa de servicio de `AL-105` se
  usa y se prueba igual; lo que espera es la ruta HTTP.
- **Las variables `ENTRA_*` vuelven a `.env.example` cuando `AL-103` las lea, no
  antes.** El barrido del 2026-08-13 encontró que estaban anunciadas y que
  `Settings` las ignoraba en silencio; volver a agregarlas sin código que las use
  reconstruiría esa misma trampa.
- **El mapeo grupos/app roles → roles de AeroLink hay que definirlo antes de
  escribir código**, no descubrirlo mientras se escribe: es la parte que decide
  quién puede descargar evidencia.
- **La llave del piloto sigue siendo el `employee_id`**, como acordó el plan
  conjunto con AeroControl: AeroLink lo guarda junto al `subject` de Entra. Queda
  por resolver si viene en un claim del token o se pide al padrón de AeroControl
  la primera vez; es detalle de `AL-103`, no de esta decisión.
