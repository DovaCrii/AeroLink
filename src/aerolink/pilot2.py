from fastapi import Response


def diagnostic_page() -> Response:
    """Return a credential-free H5 page that only detects DJI Pilot 2 JSBridge."""
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
      <p>Esta página no solicita credenciales, telemetría ni permisos de control.</p>
      <p>Resultado esperado en el control: <code>JSBridge disponible</code>.</p>
    </main>
    <script>
      const state = document.getElementById("state");
      const available = typeof window.djiBridge !== "undefined";
      state.textContent = available
        ? "JSBridge disponible: DJI Pilot 2 cargó la página AeroLink."
        : "JSBridge no detectado: esperado si se abre desde un navegador normal.";
      state.className = `state ${available ? "ok" : "wait"}`;
    </script>
  </body>
</html>"""
    return Response(
        content=page,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self'",
        },
    )
