import json

from fastapi import Response


def diagnostic_page(
    app_id: str | None = None,
    app_key: str | None = None,
    app_license: str | None = None,
) -> Response:
    """Return an H5 page that verifies a runtime license but never loads cloud control."""
    license_config = (
        {"appId": app_id, "appKey": app_key, "license": app_license}
        if all((app_id, app_key, app_license))
        else None
    )
    license_config_json = json.dumps(license_config).replace("<", "\\u003c")
    page = """<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AeroLink · Diagnóstico Pilot 2</title>
    <style>
      body { background: #07131f; color: #eef7ff; font: 16px system-ui, sans-serif; margin: 0; }
      main { max-width: 42rem; margin: 0 auto; padding: 2rem; }
      .state { border-radius: .5rem; margin: 1rem 0; padding: 1rem; }
      .ok { background: #0c3b31; } .wait { background: #3b2d0c; }
      code { color: #a7d8ff; }
    </style>
  </head>
  <body>
    <main>
      <h1>AeroLink · Diagnóstico DJI Pilot 2</h1>
      <p id="state" class="state wait">Comprobando JSBridge…</p>
      <p id="license" class="state wait">Comprobando configuración de licencia…</p>
      <p>Esta página no carga MQTT, telemetría ni permisos de control.</p>
      <p>Resultado esperado en el control: <code>JSBridge disponible</code> y,
        con el entorno configurado, <code>licencia verificada</code>.</p>
    </main>
    <script>
      const licenseConfig = __LICENSE_CONFIG__;
      const state = document.getElementById("state");
      const license = document.getElementById("license");
      const available = typeof window.djiBridge !== "undefined";
      state.textContent = available
        ? "JSBridge disponible: DJI Pilot 2 cargó la página AeroLink."
        : "JSBridge no detectado: esperado si se abre desde un navegador normal.";
      state.className = `state ${available ? "ok" : "wait"}`;
      if (!available) {
        license.textContent = "La licencia se verifica únicamente dentro de DJI Pilot 2.";
      } else if (!licenseConfig) {
        license.textContent = "Licencia no configurada en el servidor de prueba.";
      } else {
        try {
          const result = JSON.parse(window.djiBridge.platformVerifyLicense(
            licenseConfig.appId, licenseConfig.appKey, licenseConfig.license
          ));
          const verified = result.code === 0;
          license.textContent = verified
            ? "Licencia DJI verificada. No se cargó MQTT ni control remoto."
            : `La licencia DJI no fue aceptada: ${result.message || "sin detalle"}.`;
          license.className = `state ${verified ? "ok" : "wait"}`;
        } catch (error) {
          license.textContent = "No fue posible verificar la licencia DJI.";
        }
      }
    </script>
  </body>
</html>""".replace("__LICENSE_CONFIG__", license_config_json)
    return Response(
        content=page,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self'",
        },
    )
