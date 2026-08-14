# Runbook: desplegar AeroLink en p340

AeroLink comparte la VM con AeroControl y **no comparte nada más** (ADR-0001):
red y volúmenes propios de docker, base de datos propia, y ninguno escribe en el
dominio del otro. Este runbook levanta AeroLink en esa VM y lo publica por la
misma entrada HTTPS que ya funciona.

Datos verificados de la VM (2026-08-13): host `p340`, IP de tailnet
`100.121.16.118`, usuario `levdigital01`, Ubuntu Server 26.04. AeroControl corre
en `gunicorn` sobre `127.0.0.1:8000` y **Tailscale Funnel ya ocupa el 443 del nodo
en `/`** (`https://p340.tailccd107.ts.net/health/` responde 200 desde internet).

> **MagicDNS del equipo desde donde administras.** Si `ssh p340.tailccd107.ts.net`
> da *connection timed out*, no es la VM: es que el nombre resolvió a la **IP
> pública del sitio** (`200.54.29.98`), donde el 22 no está abierto —el mismo
> hallazgo de AL-003—. Usa la IP de tailnet. La causa local es
> `Tailscale failed to set the DNS configuration of your device`.

## Lo que este despliegue **no** hace

- No abre el 8883 ni ningún puerto del router: el broker sigue sin existir
  (ADR-0004). El worker se levanta igual y esperará credenciales de relay.
- No expone MinIO, Postgres ni el dashboard de EMQX: todo queda en loopback.
- No sirve de nada para probar DJI **si no se hace la Parte D** (la URL pública).

## Parte A — Código y configuración

```bash
sudo mkdir -p /opt/aerolink && sudo chown $USER:$USER /opt/aerolink
git clone https://github.com/DovaCrii/AeroLink.git /opt/aerolink
cd /opt/aerolink
cp .env.example .env && chmod 600 .env
```

`.env` **no va a Git** (`.gitignore:10`) y lo lee `docker compose` (`env_file`).
Valores que hay que poner de verdad:

| Variable | Valor en p340 |
|---|---|
| `APP_ENV` | `pilot` |
| `APP_BASE_URL` | `https://p340.tailccd107.ts.net/aerolink` |
| `APP_ROOT_PATH` | `/aerolink` |
| `APP_SECRET_KEY` | generado (abajo) |
| `POSTGRES_PASSWORD` | generado |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | generados |
| `OBJECT_STORAGE_ACCESS_KEY` / `_SECRET_KEY` | los mismos de MinIO |
| `SERVICE_TOKEN` | generado; el mismo valor va en AeroControl |
| `SERVICE_TOKEN_WORKSPACE` | el slug del workspace (p. ej. `jej`) |
| `DJI_APP_ID` / `_KEY` / `_LICENSE` | los que ya existen; **por canal de secretos, nunca por Git ni chat** |
| `MQTT_*_WORKER_*` | se dejan vacíos hasta que exista el relay |

Generar los secretos **en la máquina** (no pegarlos desde otra parte):

```bash
python3 -c "import secrets; print('APP_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('SERVICE_TOKEN=' + secrets.token_urlsafe(32))"
```

`DATABASE_URL` no se toca: `docker-compose.yml` lo sobrescribe apuntando al
servicio `postgres` con `POSTGRES_PASSWORD`.

## Parte B — Levantar el stack

```bash
cd /opt/aerolink
docker compose up --build --detach api worker minio
```

`postgres` y `migrate` entran solos como dependencias de `api`, así que no hace
falta nombrarlos.

`migrate` corre `alembic upgrade head` y los demás esperan a que termine bien
(`service_completed_successfully`). **`emqx` no se levanta**: el compose lo marca
como sólo desarrollo y en producción el broker vive en un relay externo.

```bash
docker compose ps                       # migrate = exited(0), el resto = running
docker compose logs migrate --tail 20   # debe terminar en el 20260813_0002
curl -sS http://127.0.0.1:8081/health   # {"status":"ok",...}
curl -sS http://127.0.0.1:8081/ready    # {"status":"ready","dependency":"database"}
```

Si `/ready` responde 503, es Postgres, y responde **en segundos** — no se cuelga:
el motor abre con `connect_timeout` justamente para eso.

El `worker` va a reiniciarse en bucle con `Missing relay settings: …`. **Es lo
correcto**: no tiene relay al que conectarse todavía y no tiene default al que
caer (ADR-0004). Para no ensuciar los logs mientras eso se decide:

```bash
docker compose stop worker
```

## Parte C — Crear el workspace y las baterías

El endpoint de inventario responde `503` sin `SERVICE_TOKEN` y devuelve sólo lo
del workspace que ese token nombra. El workspace hay que crearlo:

```bash
cd /opt/aerolink
docker compose exec api python -c "
from aerolink.db import SessionLocal
from aerolink.models import Workspace
with SessionLocal() as s:
    if not s.query(Workspace).filter_by(slug='jej').one_or_none():
        s.add(Workspace(slug='jej', name='JEJ'))
        s.commit()
    print([w.slug for w in s.query(Workspace)])
"
```

Las baterías se cargan después: son el dato que AeroLink masterea, y hasta que
existan el sync de AeroControl devolverá cero **legítimamente**.

## Parte D — Publicar por Funnel **sólo la superficie de diagnóstico**

Funnel sólo admite 443, 8443 y 10000, y el 443 del nodo ya sirve AeroControl en
`/`. En vez de darle a AeroLink un puerto no estándar —que la H5 de DJI podría
rechazar— se le da una **ruta** en el mismo 443.

**Lo que se publica ahí no es la API (8081).** La primera versión de este runbook
decía `8081` y eso es un error: publicar la API completa pone `/metrics`, `/docs` y
`/openapi.json` de cara a internet —verificado el 2026-08-13: los tres respondían
`200`—. El inventario de `AL-107` está protegido por token, pero las métricas no lo
están, y no hacen falta afuera: **AeroControl lee la API por loopback**, no por
Funnel.

Hay **dos** superficies H5 y la diferencia importa:

| Servicio | Puerto | Lee `.env` | Cuándo publicarlo |
|---|---|---|---|
| `pilot2-connectivity` | 8092 | **No** | Por defecto, y para la Prueba 1 |
| `pilot2-diagnostic` | 8090 | Sí | **Sólo durante** la Prueba 2, con el control en mano |

La razón es que la verificación de licencia de DJI ocurre **en el cliente**: la
página tiene que llevar `appId`, `appKey` y `license` en su propio HTML para
pasárselos a `djiBridge.platformVerifyLicense`. Es el diseño de DJI, no un defecto
nuestro, pero significa que **8090 publica esas tres credenciales a cualquiera que
haga `curl`**. `pilot2-connectivity` sirve la misma página sin credenciales —su
servicio ni siquiera monta `env_file`— y alcanza para demostrar que Pilot 2 carga la
página y expone JSBridge.

Por defecto, entonces:

```bash
cd /opt/aerolink
docker compose up --detach pilot2-connectivity
sudo tailscale funnel --bg --set-path /aerolink 8092
tailscale funnel status
```

Y **sólo mientras dure la Prueba 2**, con el control conectado:

```bash
cd /opt/aerolink
docker compose up --detach pilot2-diagnostic
sudo tailscale funnel --bg --set-path /aerolink 8090     # publica las credenciales
# ... hacer la prueba ...
sudo tailscale funnel --bg --set-path /aerolink 8092     # volver a la superficie sin credenciales
```

Comprobar qué está publicado en cada momento, sin imprimir el valor:

```bash
curl -sS https://p340.tailccd107.ts.net/aerolink | grep -c '"appKey"'
```

`0` = superficie sin credenciales. `1` = credenciales publicadas, y eso sólo debe
ser cierto mientras haya una prueba en curso.

Volver a ejecutar `--set-path /aerolink` **sobrescribe** esa ruta; no hace falta
`off` y así no se corre el riesgo de tocar la de AeroControl. `status` debe seguir
mostrando `/` → `127.0.0.1:8000`.

> **No usar `tailscale funnel --https=443 off`**, que es lo que sugiere la salida
> del comando: eso apaga el Funnel completo del nodo y **se lleva AeroControl con
> él**. Para quitar sólo esta ruta: `sudo tailscale funnel --set-path /aerolink off`.

`--set-path` recorta el prefijo antes de reenviar, así que la app recibe `/`
mientras el mundo ve `/aerolink`. `APP_ROOT_PATH=/aerolink` queda configurado para
cuando la API sí necesite servirse bajo el prefijo (su propia ruta de descarga,
con `AL-103`).

**Verificar desde fuera del tailnet** (un teléfono con datos móviles; un equipo del
tailnet llega igual con o sin Funnel, así que no sirve para comprobar la exposición):

```
https://p340.tailccd107.ts.net/aerolink       ← la H5 de diagnóstico
https://p340.tailccd107.ts.net/health/        ← AeroControl, debe seguir intacto
```

Y comprobar que la API **no** quedó expuesta:

```bash
for p in metrics docs api/v1/devices/?kind=battery; do
  curl -sS -o /dev/null -w "$p=%{http_code}\n" "https://p340.tailccd107.ts.net/aerolink/$p"
done
```

Con `pilot2-diagnostic` detrás de la ruta, las tres deben dar `404`.

Con eso el preflight de licencia deja de tener bloqueadores. **Se invoca como
módulo**: `aerolink_preflight.py` es una conveniencia para un checkout de código y
el Dockerfile no lo copia a la imagen —sólo `src/` y `alembic/`—, así que dentro
del contenedor la forma correcta es:

```bash
docker compose exec api python -m aerolink.preflight --scope license
```

## Parte E — Verificar el contrato sin depender de AeroControl

Comprobar el productor antes de culpar al consumidor. El token se lee del `.env` y
no se imprime:

```bash
cd /opt/aerolink
T=$(grep '^SERVICE_TOKEN=' .env | cut -d= -f2-)
curl -sS -H "Authorization: Token $T" "http://127.0.0.1:8081/api/v1/devices/?kind=battery"; echo
curl -sS -o /dev/null -w "aircraft=%{http_code}\n" -H "Authorization: Token $T" "http://127.0.0.1:8081/api/v1/devices/?kind=aircraft"
curl -sS -o /dev/null -w "sin_token=%{http_code}\n" "http://127.0.0.1:8081/api/v1/devices/?kind=battery"
```

Esperado: `{"results":[]}` con el inventario vacío —cero baterías es un resultado
legítimo, no una falla—, `aircraft=403` (el padrón es de AeroControl, AL-R4) y
`sin_token=401`.

## Parte F — Conectar AeroControl (Prueba 0)

En **AeroControl**, antes del primer sync real:

```bash
cd /opt/aerocontrol
set -a; source <(sudo cat /etc/aerocontrol.env); set +a
uv run python manage.py audit_serial_case      # cambiar save() no reescribe filas ya guardadas
```

Después hay que **configurar la URL y el token en AeroControl**. Este paso es fácil
de saltarse, y el síntoma es `AeroLink unavailable: AEROLINK_API_URL is not
configured`. El bloque lee el token del `.env` de AeroLink y lo escribe en
`/etc/aerocontrol.env` sin mostrarlo, y es idempotente:

```bash
sudo bash -c 'T=$(grep "^SERVICE_TOKEN=" /opt/aerolink/.env | cut -d= -f2-); sed -i "/^AEROLINK_API_URL=/d;/^AEROLINK_API_TOKEN=/d" /etc/aerocontrol.env; printf "AEROLINK_API_URL=http://127.0.0.1:8081/api/v1\nAEROLINK_API_TOKEN=%s\n" "$T" >> /etc/aerocontrol.env; chmod 600 /etc/aerocontrol.env'
```

La URL es **loopback y lleva el prefijo `/api/v1`**: el cliente de AeroControl sólo
concatena `/devices/?kind=battery`, y los dos servicios comparten VM, así que esta
llamada nunca sale a internet.

`systemctl restart` es necesario porque `systemd` pasa ese archivo por
`EnvironmentFile=`; la ejecución manual del comando necesita además el `source`:

```bash
sudo systemctl restart aerocontrol && systemctl is-active aerocontrol
cd /opt/aerocontrol
set -a; source <(sudo cat /etc/aerocontrol.env); set +a
uv run python manage.py sync_batteries
```

Sin token o con token equivocado el comando **falla ruidosamente**, no reporta
cero. Cada lectura deja un `AuditEvent` en AeroLink:

```bash
cd /opt/aerolink
docker compose exec api python -c "
from aerolink.db import SessionLocal
from aerolink.models import AuditEvent
with SessionLocal() as s:
    for e in s.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(5):
        print(e.created_at, e.action, e.actor_subject)
"
```

## Parte G — Qué mirar cuando algo falle

```bash
docker compose logs api --tail 50
curl -sS http://127.0.0.1:8081/metrics | grep aerolink_ingestion
curl -sS http://127.0.0.1:8093/metrics | grep aerolink_worker   # sólo si worker está arriba
```

`aerolink_ingestion_metrics_available 0` significa que el scrape no pudo leer la
base — mira Postgres, no la métrica.

## Parte H — Revertir

```bash
cd /opt/aerolink
docker compose down                  # detiene todo; los volúmenes quedan
sudo tailscale funnel --set-path /aerolink off
tailscale funnel status              # AeroControl en `/` debe seguir ahí
```

`docker compose down -v` **también borra los volúmenes** (Postgres y MinIO). No es
parte de revertir un despliegue; es borrar los datos.

## Pendiente que este runbook no resuelve

- **Respaldo del bucket y de la base de AeroLink.** Hoy son volúmenes de docker
  sin respaldo propio verificado. Es parte de `AL-105`, y la restauración nunca
  ensayada de esta VM sigue siendo la deuda de `AL-405`/`AL-R5`.
- **El broker.** Sin relay, o sin que la Prueba 3b de la
  [ruta de prueba](RUTA_DE_PRUEBA.md) confirme el ingreso por Funnel TCP en 8443,
  el worker no tiene a qué conectarse.
