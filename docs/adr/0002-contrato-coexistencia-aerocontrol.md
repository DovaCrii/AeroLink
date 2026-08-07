# ADR-0002: Contrato de coexistencia con AeroControl

## Estado

Propuesto — 2026-08-07. Complementa el ADR-0001, no lo revierte.

## Contexto

El ADR-0001 decidió que AeroLink es independiente y que la primera versión no
modifica, consume ni sincroniza con AeroControl. Esa decisión sigue vigente y sus
motivos se sostienen.

Pero "independiente" resolvió el **despliegue** y dejó sin resolver el
**vocabulario**. Al planificar la coexistencia desde AeroControl aparecieron tres
costos que ya se están pagando, antes de escribir una línea de integración:

1. **Inventario duplicado.** AL-203 registra topología y seriales, y `Device` es
   fuente de verdad. AeroControl ya tiene las 16 aeronaves reales con su centro de
   costo, su seguro y su documentación DGAC. Sin acuerdo previo nacen dos
   inventarios de los mismos drones, y reconciliarlos después —con datos
   acumulados— es caro.
2. **Identificador externo sin definir.** El ADR-0001 dice que cada sesión
   conserva "un identificador externo inmutable para permitir una integración
   futura", pero no dice externo *a qué*. Un identificador que nadie más reconoce
   no habilita ninguna integración.
3. **Dos identidades.** Entra ID aquí, cuentas Django allá, para las mismas ~8
   personas.

Definir el contrato ahora **no** implica implementarlo ahora. Implica que M2 no
construya sobre un supuesto que después haya que deshacer.

## Decisión

### 1. La independencia de despliegue se mantiene

Sin base de datos compartida. Sin acceso cruzado a filesystem. Redes y volúmenes
separados. El ADR-0001 sigue mandando en todo lo que decidió.

### 2. El número de serie del equipo es la llave compartida

El identificador externo del ADR-0001 se concreta: es el **serial del equipo tal
como lo reporta DJI**.

Es la única llave que existe en los tres mundos del negocio:

- la **reporta DJI** nativamente en el enlace con Pilot 2;
- la **registra la DGAC** en el certificado RPAS de cada aeronave;
- está **embebida en el repositorio documental** de la empresa, cuyas carpetas se
  llaman `CC{centro}-{serie}-{modelo}`.

**Reglas de uso:**

- Normalizar antes de comparar: mayúsculas, sin espacios.
- **Nunca calce difuso.** Nada de Levenshtein ni sustitución `O`↔`0`, por tentador
  que sea. Atribuir un vuelo a la aeronave equivocada corrompe la evidencia; la
  bandeja de excepciones (AL-306) existe justamente para lo que no calza.
- No asumir longitud fija: conviven seriales de 20 caracteres (Mavic/Matrice 4) y
  de 14 (Matrice 300).

### 3. Cada sistema es maestro de su dominio

| Dominio | Maestro | El otro sistema |
|---|---|---|
| Aeronaves, operadores, centros de costo | **AeroControl** | AeroLink lee, no escribe |
| Permisos de vuelo, documentos, vigencias | **AeroControl** | AeroLink no participa |
| Telemetría, sesiones de vuelo, evidencia | **AeroLink** | AeroControl recibe, no escribe |
| Baterías, payloads, topología de control | **AeroLink** | AeroControl lo refleja para ISO 7.1.3 |

Ninguno escribe en el dominio del otro.

### 4. La comunicación es por contrato HTTP versionado

- **Fase 1** — AeroControl expone el padrón de aeronaves y operadores como
  endpoint de solo lectura. Ya tiene DRF, autenticación por token y throttling.
- **Fase 2** — AeroLink entrega sesiones de vuelo cerradas; AeroControl las
  concilia con sus registros de vuelo.

**Degradación obligatoria:** si el padrón no responde, la sesión se persiste con
el serial crudo y se concilia después. **Una sesión de vuelo nunca se descarta por
no poder resolver la aeronave.** La disponibilidad de AeroControl no puede ser un
requisito para ingerir telemetría — eso reintroduciría por la puerta trasera el
acoplamiento que el ADR-0001 evitó.

## Consecuencias

**A favor:**

- Un solo padrón, mantenido donde ya vive y donde ya tiene su documentación DGAC.
- La integración futura queda posible sin reescribir historia, que es exactamente
  lo que el ADR-0001 quería preservar con su "identificador externo inmutable".
- AL-203 sabe contra qué comparar antes de construirse.

**En contra / costos aceptados:**

- Una dependencia de red hacia AeroControl para resolver seriales, mitigada por la
  caché local y la degradación obligatoria de arriba.
- Los seriales de AeroControl necesitan una limpieza previa: de 16 aeronaves, 11
  calzan exacto con el repositorio documental; 2 traen un espacio espurio, 2
  difieren en un carácter y 1 tiene el centro de costo distinto. La reconciliación
  se hace contra el certificado RPAS de la DGAC, que es la fuente autoritativa.
- Una aeronave del padrón es **Wingtra**, no DJI: nunca aparecerá por AeroLink. El
  contrato no asume que todo el padrón sea alcanzable por telemetría.

**Abierto:**

- **Identidad**: Entra ID vs cuentas Django. Decidir antes de AL-103.
- **Retención cruzada**: aquí 90 días de telemetría y 5 años de evidencia;
  AeroControl no tiene política escrita.
- **Respaldo**: ambos sistemas comparten VM, y esa VM tiene un respaldo diario que
  **jamás se ha restaurado**. AeroLink lo hereda y lo agrava al prometer evidencia
  probatoria a 5 años. Ver AL-R5.

## Alternativas descartadas

**Fusionar ambos sistemas.** Un consumidor MQTT permanente dentro de un monolito
Django sobre SQLite acopla el ciclo de vida de un sistema experimental al de uno en
producción diaria. El ADR-0001 ya lo rechazó con razón.

**Seguir sin contrato hasta que AeroLink madure.** El costo no es futuro: AL-203
está en M2 y construye el registro de seriales. Sin acuerdo, nace el segundo
inventario.

**Que AeroLink lea directamente la base de AeroControl.** Prohibido por el
ADR-0001. Acopla esquemas y convierte cada migración de un lado en una rotura del
otro.

## Referencias

- ADR-0001 de este repositorio (separación de despliegue).
- [`AeroControl/docs/dev/adr-0002-coexistencia-aerolink.md`](https://github.com/DovaCrii/AeroControl/blob/main/docs/dev/adr-0002-coexistencia-aerolink.md)
  — la contraparte, con el detalle del estado real de los seriales.
- `AeroControl/docs/auditoria-iso-trazabilidad.md` — cláusula 7.1.3, el punto donde
  la telemetría de AeroLink sustituye evidencia escrita a mano.
