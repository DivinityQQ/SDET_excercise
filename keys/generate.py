"""Generate a local development RSA key pair for JWT signing/verification."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


KEYS_DIR = Path(__file__).resolve().parent
PRIVATE_KEY_PATH = KEYS_DIR / "dev.private.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "dev.public.pem"


def main() -> int:
    """Generate keys once and skip when both files already exist."""
    private_exists = PRIVATE_KEY_PATH.exists()
    public_exists = PUBLIC_KEY_PATH.exists()

    if private_exists and public_exists:
        print(f"Keys already exist, skipping: {PRIVATE_KEY_PATH} / {PUBLIC_KEY_PATH}")
        return 0

    if private_exists != public_exists:
        raise SystemExit(
            "Only one key file exists. Remove both key files and run this script again."
        )

    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    PRIVATE_KEY_PATH.write_bytes(private_pem)
    PUBLIC_KEY_PATH.write_bytes(public_pem)
    print(f"Generated: {PRIVATE_KEY_PATH}")
    print(f"Generated: {PUBLIC_KEY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
