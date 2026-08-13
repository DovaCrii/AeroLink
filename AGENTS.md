# AeroLink — guía de trabajo

- `main` debe permanecer desplegable y protegida.
- Usar ramas `codex/<area>-<descripcion>` y un PR por issue/bloque.
- No guardar secretos, credenciales DJI, telemetría real, seriales reales ni
  evidencia operacional en Git.
- Las reglas de dominio deben vivir en servicios/modelos, no solo en la UI.
- Toda API nueva requiere autenticación, autorización, auditoría y pruebas.
- Todo cambio de esquema requiere migración y prueba de regresión.
- Los payloads DJI reales se reemplazan por fixtures anonimizados.
- El gate mínimo antes de fusionar será CI verde, pruebas, lint, formato y
  análisis de dependencias.
- La integración con AeroControl requiere un plan separado en su propio
  repositorio, como estableció el ADR-0001. **Ese plan existe desde el
  2026-08-12**: `AeroControl/docs/dev/plan-integracion-aerolink.md`, con el
  contrato técnico en su ADR-0002 y el de este lado en `docs/adr/0003`. Lo
  habilitado es **únicamente** lo que ese plan enumera (hoy `AL-107`, el
  inventario de dispositivos); cualquier otra superficie de integración sigue
  fuera de alcance hasta que el plan la incluya.

