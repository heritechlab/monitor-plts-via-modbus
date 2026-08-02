from app.core.security import generate_api_key, hash_api_key, verify_api_key


def test_api_key_round_trip() -> None:
    key = generate_api_key()
    assert key.startswith("plts_")
    assert len(hash_api_key(key)) == 64
    assert verify_api_key(key, hash_api_key(key))
    assert not verify_api_key(f"{key}x", hash_api_key(key))
