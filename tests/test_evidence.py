"""AL-105: la evidencia y su hash, incluido lo que pasa cuando el bucket falla."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from aerolink.config import Settings
from aerolink.evidence import (
    EvidenceIntegrityError,
    evidence_object_key,
    expired_evidence,
    read_evidence,
    store_evidence,
)
from aerolink.models import AuditEvent, FlightEvidence
from aerolink.storage import ObjectStorageError, build_evidence_store

PAYLOAD = b"flight-log-bytes"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


class FakeStore:
    """An in-memory stand-in for the bucket, and a record of what was written."""

    def __init__(self, *, fail_on_put: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[str] = []
        self._fail_on_put = fail_on_put

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        if self._fail_on_put:
            raise ObjectStorageError("bucket unreachable")
        self.objects[key] = data
        self.puts.append(key)

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects


def test_the_object_key_is_the_digest_not_the_filename():
    key = evidence_object_key("jej", DIGEST, "FlightRecord_2026.LOG")

    # Sharded by the first byte, and the extension is decoration: two files with
    # different names but identical bytes must land on the same object.
    assert key == f"jej/{DIGEST[:2]}/{DIGEST}.log"
    assert evidence_object_key("jej", DIGEST, "otro-nombre.log") == key


def test_storing_evidence_records_the_hash_and_audits_it(db_session, workspace):
    store = FakeStore()

    evidence = store_evidence(
        db_session,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        filename="flight.log",
        data=PAYLOAD,
        store=store,
        content_type="text/plain",
        actor_subject="svc:test",
    )
    db_session.commit()

    assert evidence.sha256 == DIGEST
    assert store.objects[evidence.object_key] == PAYLOAD
    audit = db_session.query(AuditEvent).filter_by(action="evidence.stored").one()
    assert audit.resource_id == DIGEST
    assert audit.metadata_json["bytes"] == len(PAYLOAD)


def test_the_same_bytes_twice_are_one_row_and_one_upload(db_session, workspace):
    store = FakeStore()
    kwargs = {
        "workspace_id": workspace.id,
        "workspace_slug": workspace.slug,
        "filename": "flight.log",
        "data": PAYLOAD,
        "store": store,
    }

    first = store_evidence(db_session, **kwargs)
    db_session.commit()
    second = store_evidence(db_session, **{**kwargs, "filename": "copia.log"})
    db_session.commit()

    assert first.id == second.id
    # One upload, not two: the digest already identified these bytes as evidence.
    assert store.puts == [first.object_key]
    assert db_session.query(FlightEvidence).count() == 1


def test_a_failed_upload_leaves_no_row_pointing_at_nothing(db_session, workspace):
    """The database must never claim evidence the bucket does not have."""
    store = FakeStore(fail_on_put=True)

    with pytest.raises(ObjectStorageError):
        store_evidence(
            db_session,
            workspace_id=workspace.id,
            workspace_slug=workspace.slug,
            filename="flight.log",
            data=PAYLOAD,
            store=store,
        )
    db_session.rollback()

    assert db_session.query(FlightEvidence).count() == 0


def test_reading_evidence_verifies_the_digest_and_audits_the_read(
    db_session, workspace
):
    store = FakeStore()
    evidence = store_evidence(
        db_session,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        filename="flight.log",
        data=PAYLOAD,
        store=store,
    )
    db_session.commit()

    assert read_evidence(db_session, evidence=evidence, store=store) == PAYLOAD
    db_session.commit()

    assert db_session.query(AuditEvent).filter_by(action="evidence.read").count() == 1


def test_a_corrupted_object_raises_instead_of_returning_bytes(db_session, workspace):
    """Verifying at write time proves it *was* intact; this is what proves it is."""
    store = FakeStore()
    evidence = store_evidence(
        db_session,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        filename="flight.log",
        data=PAYLOAD,
        store=store,
    )
    db_session.commit()
    store.objects[evidence.object_key] = b"tampered"

    with pytest.raises(EvidenceIntegrityError):
        read_evidence(db_session, evidence=evidence, store=store)


def test_retention_finds_what_is_past_the_window_and_nothing_else(
    db_session, workspace
):
    now = datetime.now(UTC)
    old = FlightEvidence(
        workspace_id=workspace.id,
        object_key="jej/aa/old",
        original_filename="old.log",
        sha256="a" * 64,
        received_at=now - timedelta(days=1826),
    )
    recent = FlightEvidence(
        workspace_id=workspace.id,
        object_key="jej/bb/recent",
        original_filename="recent.log",
        sha256="b" * 64,
        received_at=now - timedelta(days=10),
    )
    db_session.add_all([old, recent])
    db_session.commit()

    expired = expired_evidence(db_session, retention_days=1825, now=now)

    assert [item.object_key for item in expired] == ["jej/aa/old"]
    # Nothing was deleted: the window is a query, and removing five-year evidence
    # is an explicit operation for after AL-405 proves a restore works.
    assert db_session.query(FlightEvidence).count() == 2


def test_the_store_refuses_to_build_without_credentials():
    """An anonymous client would write evidence nobody authenticated for."""
    with pytest.raises(ObjectStorageError):
        build_evidence_store(Settings(object_storage_access_key=None))
