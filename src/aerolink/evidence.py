"""Storing flight evidence with a verifiable hash (AL-105).

`FlightEvidence` has been a model and a table since the initial migration with no
writer, and the pilot acceptance criteria depend on it: *"el mensaje original y la
evidencia descargada conservan un hash verificable"*. This is that writer.

Three decisions worth stating, because each one is a place where the obvious
implementation would be wrong:

**The key is the hash.** `object_key` is derived from the SHA-256 of the bytes, so
the same file stored twice lands on the same object and the second store returns
the existing row instead of duplicating it. The unique constraint on
`(workspace_id, sha256)` already said this was the intent; content addressing is
what makes the database and the bucket agree without a second source of truth.

**Upload first, row second.** If the upload fails there is no row, so the database
never points at an object that is not there. The inverse failure — object stored,
row never written — leaves an orphan object, which is inert: it costs storage and
nothing claims it exists. A row pointing at nothing would break the evidence
promise; an unclaimed object does not.

**Retention is a query, not a purge.** `expired_evidence` finds what is past the
window; nothing here deletes. Evidence with a five-year retention should not be
removed by a background job that nobody watched, and AeroLink's restore from
backup has never been exercised (AL-405/AL-R5). Deleting is an explicit,
supervised operation for after that.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerolink.audit import record_audit
from aerolink.models import FlightEvidence
from aerolink.storage import EvidenceStore

logger = logging.getLogger("aerolink.evidence")


class EvidenceIntegrityError(RuntimeError):
    """Raised when a stored object no longer matches its recorded digest."""


def evidence_object_key(workspace_slug: str, digest: str, filename: str) -> str:
    """`<workspace>/<aa>/<sha256><ext>` — sharded by the first byte of the digest.

    The two-character prefix keeps a flat listing usable once there are many
    objects, and the extension is kept only so a human downloading the object
    gets a file their tools recognise. It is decoration: identity is the digest.
    """
    suffix = ""
    if "." in filename:
        suffix = "." + filename.rsplit(".", 1)[1].lower()
    return f"{workspace_slug}/{digest[:2]}/{digest}{suffix}"


def store_evidence(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    workspace_slug: str,
    filename: str,
    data: bytes,
    store: EvidenceStore,
    flight_session_id: uuid.UUID | None = None,
    content_type: str | None = None,
    actor_subject: str | None = None,
) -> FlightEvidence:
    """Store `data` and record it. Returns the existing row for known bytes.

    The caller commits: the audit row and the evidence row belong to the same
    transaction, following the convention `audit.py` set.
    """
    digest = hashlib.sha256(data).hexdigest()
    existing = session.scalars(
        select(FlightEvidence).where(
            FlightEvidence.workspace_id == workspace_id,
            FlightEvidence.sha256 == digest,
        )
    ).one_or_none()
    if existing is not None:
        # Not an error and not a second row: the bytes are already evidence, and
        # re-uploading them would only rewrite an identical object.
        logger.info(
            "evidence_already_stored",
            extra={"workspace_id": str(workspace_id), "topic": existing.object_key},
        )
        return existing

    object_key = evidence_object_key(workspace_slug, digest, filename)
    store.put(object_key, data, content_type=content_type)

    evidence = FlightEvidence(
        workspace_id=workspace_id,
        flight_session_id=flight_session_id,
        object_key=object_key,
        original_filename=filename,
        content_type=content_type,
        sha256=digest,
    )
    session.add(evidence)
    record_audit(
        session,
        workspace_id=workspace_id,
        actor_subject=actor_subject,
        action="evidence.stored",
        resource_type="flight_evidence",
        resource_id=digest,
        metadata={"object_key": object_key, "bytes": len(data)},
    )
    logger.info(
        "evidence_stored",
        extra={"workspace_id": str(workspace_id), "topic": object_key},
    )
    return evidence


def read_evidence(
    session: Session,
    *,
    evidence: FlightEvidence,
    store: EvidenceStore,
    actor_subject: str | None = None,
) -> bytes:
    """Read the object back and verify it still hashes to what was recorded.

    Verifying on read is the point of the whole feature: evidence whose hash is
    only checked at write time proves that it *was* intact, not that it *is*. A
    mismatch raises instead of returning bytes -- handing back content that does
    not match the recorded digest would launder a corrupted object into a report.

    A mismatch is logged, not audited. The audit row would live in the caller's
    transaction and a caller that rolls back on the exception -- the reasonable
    thing to do -- would erase the very record of the failure. Recording it
    durably needs its own transaction, and that belongs with the read endpoint
    that owns one; the endpoint waits for authentication (AL-103).
    """
    data = store.get(evidence.object_key)
    digest = hashlib.sha256(data).hexdigest()
    if digest != evidence.sha256:
        logger.error(
            "evidence_hash_mismatch",
            extra={
                "workspace_id": str(evidence.workspace_id),
                "topic": evidence.object_key,
            },
        )
        raise EvidenceIntegrityError(
            f"{evidence.object_key} hashes to {digest}, recorded as {evidence.sha256}"
        )

    record_audit(
        session,
        workspace_id=evidence.workspace_id,
        actor_subject=actor_subject,
        action="evidence.read",
        resource_type="flight_evidence",
        resource_id=evidence.sha256,
        metadata={"object_key": evidence.object_key},
    )
    return data


def expired_evidence(
    session: Session, *, retention_days: int, now: datetime
) -> list[FlightEvidence]:
    """Evidence past its retention window. Finds; does not delete.

    Kept as a query so the retention policy is inspectable —and reviewable— before
    anything acts on it. See the module docstring for why nothing here deletes.
    """
    cutoff = now - timedelta(days=retention_days)
    return list(
        session.scalars(
            select(FlightEvidence).where(FlightEvidence.received_at < cutoff)
        )
    )
