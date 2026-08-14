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
docker compose up --build --detach api worker migrate postgres minio
```

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

## Parte D — Publicar por Funnel, sin pelear con AeroControl

Funnel sólo admite 443, 8443 y 10000, y el 443 del nodo ya sirve AeroControl en
`/`. En vez de darle a AeroLink un puerto no estándar —que la H5 de DJI podría
rechazar— se le da una **ruta** en el mismo 443:

```bash
sudo tailscale funnel --bg --set-path /aerolink 8081
tailscale funnel status
```

`--set-path` recorta el prefijo antes de reenviar, así que AeroLink recibe `/health`
mientras el mundo ve `/aerolink/health`. Por eso `APP_ROOT_PATH=/aerolink`: sin él
la app responde igual pero genera URLs sin el prefijo.

**Verificar desde fuera del tailnet** (un teléfono con datos móviles; un equipo del
tailnet llega igual con o sin Funnel, así que no sirve para comprobar la exposición):

```
https://p340.tailccd107.ts.net/aerolink/health
https://p340.tailccd107.ts.net/aerolink/pilot2/diagnostic
https://p340.tailccd107.ts.net/health/          ← AeroControl, debe seguir intacto
```

Con eso el preflight de licencia deja de tener bloqueadores:

```bash
docker compose exec api python aerolink_preflight.py --scope license
```

## Parte E — Conectar AeroControl (Prueba 0)

En **AeroControl**, antes del primer sync real:

```bash
cd /opt/aerocontrol
set -a; source <(sudo cat /etc/aerocontrol.env); set +a
uv run python manage.py audit_serial_case      # cambiar save() no reescribe filas ya guardadas
```

Configurar la URL y el token —el mismo valor generado en la Parte A— y sincronizar:

```bash
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

## Parte F — Qué mirar cuando algo falle

```bash
docker compose logs api --tail 50
curl -sS http://127.0.0.1:8081/metrics | grep aerolink_ingestion
curl -sS http://127.0.0.1:8093/metrics | grep aerolink_worker   # sólo si worker está arriba
```

`aerolink_ingestion_metrics_available 0` significa que el scrape no pudo leer la
base — mira Postgres, no la métrica.

## Parte G — Revertir

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
