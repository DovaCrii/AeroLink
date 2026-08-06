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
- La integración con AeroControl está fuera de alcance hasta crear un plan
  separado en su propio repositorio.

