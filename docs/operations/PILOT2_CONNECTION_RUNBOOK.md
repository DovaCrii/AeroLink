# Runbook: primera prueba de conexión DJI Pilot 2

## Objetivo y límite

La primera prueba demuestra que un control DJI carga AeroLink, valida su
licencia, establece MQTTS y queda online. Es una prueba de conectividad y
registro: no se habilitan comandos remotos, despegue, misiones ni control de
vuelo.

## Información que debe aportar la operación

1. Una combinación elegida de aeronave y control:
   - Mavic 3E con DJI RC Pro Enterprise; o
   - Matrice 4E/4T con DJI RC Plus 2.
2. Modelo del control, firmware de aeronave y control, y versión de DJI Pilot 2.
3. Acceso al portal DJI Developer para crear una aplicación de tipo Cloud API.
4. `DJI_APP_ID`, `DJI_APP_KEY` y `DJI_APP_LICENSE`. Entrégalos solo mediante el
   canal de secretos aprobado; nunca por Git, issue, chat o captura.
5. Un FQDN exclusivo para la prueba, certificado TLS válido y una red desde la
   que el control alcance HTTPS 443 y MQTTS 8883.

La documentación oficial de DJI lista esas combinaciones de equipos y versiones
mínimas actualizadas en su página de compatibilidad. El H5 usa JSBridge para
verificar la licencia y entregar a Pilot 2 los datos de conexión MQTT.

## Preparar el servidor

1. Desplegar el PR base de AeroLink en un entorno de prueba aislado.
2. Crear un `.env` fuera de Git usando `.env.example` como base.
3. Configurar como mínimo:

   ```dotenv
   APP_ENV=pilot
   APP_BASE_URL=https://pilot.aerolink.example
   DJI_APP_ID=<secreto>
   DJI_APP_KEY=<secreto>
   DJI_APP_LICENSE=<secreto>
   MQTT_PUBLIC_HOST=mqtt.aerolink.example
   MQTT_TLS_PORT=8883
   MQTT_TLS_CERT_FILE=<ruta-local-al-certificado>
   MQTT_TLS_KEY_FILE=<ruta-local-a-la-clave>
   ```

4. Ejecutar el preflight, que no abre conexiones externas ni muestra secretos:

   ```powershell
   uv run python aerolink_preflight.py
   ```

   Debe terminar sin elementos `blocker`.
5. Verificar localmente antes de exponer nada:

   ```powershell
   docker compose up --build
   curl http://127.0.0.1:8081/health
   curl http://127.0.0.1:8081/ready
   ```

6. Configurar el listener TLS de EMQX en 8883, sin MQTT anónimo y con ACL por
   dispositivo. Mantener el dashboard de EMQX fuera de Internet. El certificado
   debe incluir la cadena intermedia completa.

## Prueba controlada con el control

1. Confirmar que el control tiene conectividad a los FQDN de HTTPS y MQTTS.
2. En DJI Pilot 2, abrir el portal Cloud Services y cargar la página H5
   configurada para AeroLink.
3. Abrir `https://<FQDN>/pilot2/diagnostic`. El resultado esperado es
   **"JSBridge disponible"** y **"Licencia DJI verificada"**. En un navegador
   normal se espera que JSBridge no esté disponible. La página toma las
   credenciales solo desde el entorno de ejecución, no las persiste ni las
   registra; DJI requiere esas tres credenciales para la verificación H5.
4. El siguiente hito, AL-202, entrega las credenciales MQTT por dispositivo y
   carga el Cloud Module. Solo entonces comprobar que el control queda online en
   el broker y que se registra un evento de conexión.
5. Detener la prueba si falla el certificado, la licencia, autenticación MQTT o
   cualquier ACL. No realizar un despegue como parte de esta prueba.

## Evidencia mínima de aceptación

- Captura anonimizada de la página de diagnóstico en Pilot 2.
- Resultado sin bloqueadores de `aerolink.preflight`.
- Registro de conexión del broker, sin credenciales ni seriales.
- Firmware, Pilot 2 y modelo de control anotados en el inventario interno.

## Reversión

Deshabilitar la configuración Cloud Services del control, revocar la credencial
MQTT asignada al dispositivo y retirar la regla pública de 8883. Conservar solo
los logs y auditoría permitidos por la política de retención.
