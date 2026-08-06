# ADR-0001: AeroLink independiente de AeroControl

## Decisión

AeroLink será un repositorio y despliegue independiente. La primera versión no
modifica, consume ni sincroniza con AeroControl.

## Motivos

- MQTT y telemetría son procesos continuos y asíncronos.
- DJI requiere ingreso público específico y credenciales propias.
- El fallo de ingesta no debe afectar el sistema operacional existente.
- AeroControl conserva su ciclo de estabilización y su despliegue actual.

## Consecuencia

AeroLink mantiene sus propios identificadores, vuelos, usuarios, equipos,
telemetría y evidencia. La futura integración se diseña como un proyecto aparte
en `DovaCrii/AeroControl`, con contratos versionados y sin compartir base de
datos.

