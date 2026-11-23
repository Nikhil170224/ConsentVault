from app.core.logging import mask_pii
from app.core.permissions import Permission, has_permission
from app.core.security import hash_password, hash_pii, verify_password
from app.middleware.rate_limit import InMemoryRateLimiter


def test_password_hashing():
    hashed = hash_password("Password123!")
    assert hashed != "Password123!"
    assert verify_password("Password123!", hashed)
    assert not verify_password("wrong", hashed)


def test_pii_masking():
    masked = mask_pii("user john.doe@example.com from 192.168.1.10 logged in")
    assert "john.doe@example.com" not in masked
    assert "192.168.1.10" not in masked
    assert "@example.com" in masked


def test_anonymization_hash_is_irreversible_and_stable():
    h = hash_pii("someone@example.com")
    assert h.startswith("anon_")
    assert "someone" not in h
    assert h == hash_pii("someone@example.com")
    assert h != hash_pii("other@example.com")


def test_role_permission_matrix():
    assert has_permission("super_admin", Permission.ORG_MANAGE)
    assert has_permission("org_admin", Permission.CONSENT_MANAGE)
    assert not has_permission("dpo", Permission.CONSENT_MANAGE)
    assert has_permission("dpo", Permission.AUDIT_READ)
    assert has_permission("data_subject", Permission.DSR_CREATE)
    assert not has_permission("data_subject", Permission.REPORT_READ)


def test_rate_limiter_blocks_after_limit():
    rl = InMemoryRateLimiter()
    assert all(rl.allow("k", 3) for _ in range(3))
    assert not rl.allow("k", 3)
    assert rl.allow("other", 3)
