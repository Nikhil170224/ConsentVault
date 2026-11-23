from app.core.security import sign_webhook_payload, verify_webhook_signature
from app.services.webhook_service import MAX_ATTEMPTS, backoff_seconds


def test_signature_roundtrip():
    body = b'{"event":"consent.granted"}'
    sig = sign_webhook_payload(body, "topsecret")
    assert verify_webhook_signature(body, "topsecret", sig)


def test_signature_rejects_tampered_body():
    sig = sign_webhook_payload(b'{"a":1}', "topsecret")
    assert not verify_webhook_signature(b'{"a":2}', "topsecret", sig)


def test_signature_rejects_wrong_secret():
    body = b"payload"
    sig = sign_webhook_payload(body, "secret-one")
    assert not verify_webhook_signature(body, "secret-two", sig)


def test_backoff_is_exponential():
    assert [backoff_seconds(i) for i in (1, 2, 3, 4, 5)] == [2, 4, 8, 16, 32]
    assert MAX_ATTEMPTS == 5
