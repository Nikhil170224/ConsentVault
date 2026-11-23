import uuid

from app.services.audit_service import GENESIS_HASH, canonical_payload, compute_event_hash


def test_canonical_payload_is_deterministic():
    a = canonical_payload({"b": 2, "a": 1})
    b = canonical_payload({"a": 1, "b": 2})
    assert a == b == '{"a":1,"b":2}'


def test_hash_changes_with_prev_hash():
    payload = {"event_type": "consent.granted"}
    h1 = compute_event_hash(GENESIS_HASH, payload)
    h2 = compute_event_hash("f" * 64, payload)
    assert h1 != h2
    assert len(h1) == 64


def test_hash_changes_with_payload():
    h1 = compute_event_hash(GENESIS_HASH, {"new_status": "GRANTED"})
    h2 = compute_event_hash(GENESIS_HASH, {"new_status": "WITHDRAWN"})
    assert h1 != h2


def test_genesis_hash_is_zeros():
    assert GENESIS_HASH == "0" * 64
    assert uuid.UUID(int=0) is not None
