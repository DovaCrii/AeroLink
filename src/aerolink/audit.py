"""Writing `AuditEvent` rows — the first writer in the repo (AL-107).

`AuditEvent` has existed as a model and a table since the initial migration and
nothing ever wrote to it. This is the helper every later endpoint should use, so
the conventions it establishes are worth stating rather than inferring:

- `action` is `<dominio>.<verbo>`, lower-case dotted (`inventory.read`).
- `resource_type` is the singular model name (`device`).
- `resource_id` is `None` for a collection: a list read has no single resource,
  and stuffing the collection name there would make the column mean two things.
  Anything else about the call goes in `metadata_json`.

**Reads are audited too, deliberately.** The access log already records that a
request happened, but this is a disclosure across a trust boundary — the fleet
inventory leaving AeroLink for another system — and AeroControl's mirrored
battery table is ISO 7.1.3 *evidence*. When an auditor asks where a cycle count
came from and when, this row is the artifact that answers; a line in a rotating
stdout log is not.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from aerolink.models import AuditEvent


def record_audit(
    session: Session,
    *,
    workspace_id: uuid.UUID | None,
    actor_subject: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    """Add an audit row to `session`. The caller commits it.

    Deliberately not committing here: the row belongs to the same transaction as
    whatever it describes, so a failure to record means the request fails and
    nothing is disclosed. Returning data you could not record is the failure ISO
    actually cares about.
    """
    event = AuditEvent(
        workspace_id=workspace_id,
        actor_subject=actor_subject,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
    )
    session.add(event)
    return event
