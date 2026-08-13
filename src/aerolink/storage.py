"""The object store behind the evidence (AL-105).

One adapter, so boto3 appears in exactly one module and everything above it —
including the tests — talks to `EvidenceStore`. That boundary is what makes the
service layer testable without a bucket, and what would make a move from MinIO
on p340 to a real S3 a configuration change.

Deliberately narrow: put, get, exists. No delete. Nothing in AeroLink removes
evidence automatically — see `evidence.py` for why the retention window is a
query and not a purge.
"""

from __future__ import annotations

import logging
from typing import Protocol

from aerolink.config import Settings

logger = logging.getLogger("aerolink.storage")


class ObjectStorageError(RuntimeError):
    """Raised when the object store cannot be reached or refuses a write."""


class EvidenceStore(Protocol):
    """What the evidence service needs from a store. Implemented by `S3EvidenceStore`
    in production and by a fake in the tests."""

    def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class S3EvidenceStore:
    """S3-compatible implementation. Errors are wrapped so callers never have to
    import botocore to handle a failure."""

    def __init__(self, client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra)
        except Exception as error:  # botocore raises a family, not one class
            raise ObjectStorageError(f"could not store {key}") from error

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except Exception as error:
            raise ObjectStorageError(f"could not read {key}") from error

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            # A missing object and an unreachable bucket look the same to the
            # caller on purpose: this only decides whether to re-upload, and
            # re-uploading byte-identical content is harmless either way. Logged
            # so the difference is still recoverable when it matters.
            logger.debug("evidence_head_failed", extra={"topic": key}, exc_info=True)
            return False


def build_evidence_store(settings: Settings) -> S3EvidenceStore:
    """Build the production store. Fails closed when credentials are missing.

    An anonymous client would "work" against a permissive bucket and silently
    write evidence nobody authenticated for. Refusing is the safer failure: the
    caller sees a configuration error instead of a five-year retention promise
    resting on an open bucket.
    """
    if not settings.object_storage_access_key or not settings.object_storage_secret_key:
        raise ObjectStorageError(
            "OBJECT_STORAGE_ACCESS_KEY and OBJECT_STORAGE_SECRET_KEY are required; "
            "AeroLink does not fall back to an anonymous client for evidence."
        )

    import boto3  # imported here so the rest of the app does not pay for it

    client = boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
    )
    logger.info("evidence_store_ready", extra={"topic": settings.object_storage_bucket})
    return S3EvidenceStore(client, settings.object_storage_bucket)
