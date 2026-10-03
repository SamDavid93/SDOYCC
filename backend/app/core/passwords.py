"""Salted scrypt passwords; no plaintext passwords are stored."""
import hashlib
import secrets

N, R, P = 131072, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, maxmem=256 * 1024 * 1024)
    return f"scrypt${N}${R}${P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    # Perform the same expensive operation for unknown/unregistered accounts.
    stored = stored or f"scrypt${N}${R}${P}${'00' * 16}${'00' * 64}"
    try:
        algorithm, n, r, p, salt, expected = stored.split("$")
        if (algorithm, int(n), int(r), int(p)) != ("scrypt", N, R, P):
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=N, r=R, p=P, maxmem=256 * 1024 * 1024)
        return secrets.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False
