import hashlib
import hmac
import secrets


def generate_api_key() -> str:
    return f"plts_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    # API key dibuat acak berentropi tinggi, sehingga SHA-256 sesuai untuk lookup aman.
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_prefix(api_key: str) -> str:
    return api_key[:12]


def verify_api_key(api_key: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(api_key), expected_hash)
