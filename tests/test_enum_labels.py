"""Los tipos enumerados de la base tienen que llevar los valores, no los nombres.

Esta prueba existe por un 500 en producción, no por completitud. El 2026-08-13, en
p340, `GET /api/v1/devices/?kind=battery` respondió `Internal Server Error` mientras
`?kind=aircraft` daba 403 y sin token daba 401: la autenticación funcionaba y la
consulta se caía. La causa es que `Enum(PyEnum)` de SQLAlchemy persiste
`member.name` por omisión —`"BATTERY"`— y la migración inicial creó los tipos
Postgres con los valores en minúscula, así que la comparación era un
`invalid input value for enum device_kind`.

Las 51 pruebas de entonces pasaban porque sqlite degrada `Enum` a VARCHAR con un
CHECK, y ahí ambos lados coincidían en el nombre. Es decir: **la suite no podía ver
este defecto**, y por eso la comprobación no mira una consulta sino las etiquetas
declaradas, que es lo que Postgres realmente compara.

Si algún día se agrega Postgres a CI, esta prueba se vuelve redundante. Hasta
entonces es lo único que separa este error de volver a producción.
"""

from aerolink.models import Device, DeviceKind, UserIdentity, UserRole

# Copiadas a mano de `alembic/versions/20260806_0001_initial_domain.py`, que es
# quien crea los tipos en Postgres. Si cambian allá, esto tiene que fallar.
MIGRATION_DEVICE_KIND_LABELS = ("controller", "aircraft", "payload", "battery")
MIGRATION_USER_ROLE_LABELS = ("administrator", "operations", "pilot", "viewer")


def test_device_kind_labels_match_the_migration():
    assert set(Device.__table__.c.kind.type.enums) == set(MIGRATION_DEVICE_KIND_LABELS)


def test_user_role_labels_match_the_migration():
    assert set(UserIdentity.__table__.c.role.type.enums) == set(
        MIGRATION_USER_ROLE_LABELS
    )


def test_what_postgres_actually_receives_is_the_value():
    """La comprobación más cercana al defecto real, sin necesitar una base.

    Antes de la corrección esto devolvía `"BATTERY"`, que es exactamente el valor
    que Postgres rechazaba con `invalid input value for enum device_kind`.
    """
    from sqlalchemy.dialects import postgresql

    dialect = postgresql.dialect()
    kind_bind = Device.__table__.c.kind.type.bind_processor(dialect)
    role_bind = UserIdentity.__table__.c.role.type.bind_processor(dialect)

    assert kind_bind(DeviceKind.BATTERY) == "battery"
    assert role_bind(UserRole.ADMINISTRATOR) == "administrator"


def test_the_labels_are_the_values_and_not_the_member_names():
    """La forma en que este defecto se vería de nuevo: nombres en mayúscula."""
    assert set(Device.__table__.c.kind.type.enums) == {k.value for k in DeviceKind}
    assert set(UserIdentity.__table__.c.role.type.enums) == {r.value for r in UserRole}
    assert "BATTERY" not in Device.__table__.c.kind.type.enums
    assert "ADMINISTRATOR" not in UserIdentity.__table__.c.role.type.enums
