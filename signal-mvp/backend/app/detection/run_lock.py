"""Cross-worker coordination for active patient detection runs."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import text


class PatientDetectionLease:
    """A PostgreSQL session advisory lock held on a checked-out connection."""

    def __init__(self, connection: Any, lock_key: int) -> None:
        self._connection = connection
        self._lock_key = lock_key
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            self._connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": self._lock_key},
            )
            self._connection.commit()
        except Exception:
            # A checked-in pooled connection must never retain a session lock.
            self._connection.invalidate()
            raise
        finally:
            # Closing the checked-out connection also releases a session lock
            # if PostgreSQL reports an error while explicitly unlocking it.
            self._connection.close()


def _patient_lock_key(patient_id: UUID | str, purpose: str = "detection") -> int:
    digest = hashlib.sha256(f"signal:{purpose}:{patient_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def try_acquire_patient_detection_lease(engine: Any, patient_id: UUID | str) -> PatientDetectionLease | None:
    """Return a cross-process lease, or ``None`` if the patient is already running."""

    return _try_acquire_lease(engine, _patient_lock_key(patient_id, "detection"))


def try_acquire_patient_anatomy_lease(engine: Any, patient_id: UUID | str) -> PatientDetectionLease | None:
    """Coordinate expensive anatomy extraction independently of detection."""

    return _try_acquire_lease(engine, _patient_lock_key(patient_id, "anatomy"))


def _try_acquire_lease(engine: Any, lock_key: int) -> PatientDetectionLease | None:
    connection = engine.connect()
    try:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": lock_key},
        ).scalar()
        # Close the transaction while retaining PostgreSQL's session-level
        # advisory lock on this checked-out physical connection.
        connection.commit()
        if not acquired:
            connection.close()
            return None
        return PatientDetectionLease(connection, lock_key)
    except Exception:
        try:
            connection.invalidate()
        finally:
            connection.close()
        raise
