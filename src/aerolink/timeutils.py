"""One place where a timestamp from the database becomes comparable.

Every column is `DateTime(timezone=True)` and every write goes through
`datetime.now(UTC)`, so the values *are* UTC. What varies is whether the driver
says so: Postgres returns them timezone-aware, sqlite returns them naive. Mixing
the two raises `TypeError: can't compare offset-naive and offset-aware datetimes`
at the moment of comparison — which is to say, in production, the first time an
observation is seen twice.

`as_utc` is the fix, and it lives here rather than inline because the assumption
it encodes (*naive means UTC, because that is how it was written*) is one that
must be stated once and shared, not re-derived by each caller.
"""

from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """The same instant, guaranteed timezone-aware in UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
