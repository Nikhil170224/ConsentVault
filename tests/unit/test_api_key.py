from app.core.security import generate_api_key, hash_api_key, verify_api_key


def test_generated_key_format():
    raw, prefix, key_hash = generate_api_key()
    assert raw.startswith("cv_")
    assert raw.startswith(prefix)
    assert key_hash == hash_api_key(raw)
    assert len(key_hash) == 64


def test_verify_accepts_correct_key():
    raw, _, key_hash = generate_api_key()
    assert verify_api_key(raw, key_hash)


def test_verify_rejects_wrong_key():
    raw, _, key_hash = generate_api_key()
    assert not verify_api_key(raw + "x", key_hash)
    assert not verify_api_key("cv_wrong", key_hash)


def test_keys_are_unique():
    keys = {generate_api_key()[0] for _ in range(50)}
    assert len(keys) == 50
