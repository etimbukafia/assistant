"""
Encryption utilities for sensitive data at rest

Uses Fernet (symmetric encryption) to encrypt:
- OAuth tokens before storing in database
- Email body content for privacy

Encryption key is stored in environment variable for security.

Fernet provides:
- AES-128 encryption in CBC mode
- HMAC for authentication (prevents tampering)
- Timestamps for expiration
"""
from cryptography.fernet import Fernet

from .config import settings


def get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable

    If not set, generates a new key and prints warning.
    In production, this should be set in .env file.

    Returns:
        bytes: Encryption key
    """
    key = settings.ENCRYPTION_KEY

    if not key:
        # Generate new key for first-time setup
        new_key = Fernet.generate_key()
        print("\n" + "="*60)
        print("⚠️  WARNING: ENCRYPTION_KEY not set in .env!")
        print("="*60)
        print("\nGenerated a new encryption key. Add this to your .env file:")
        print(f"\nENCRYPTION_KEY={new_key.decode()}")
        print("\n⚠️  IMPORTANT: Save this key securely!")
        print("   - Without it, you cannot decrypt stored tokens")
        print("   - Losing it means users must re-authorize Gmail")
        print("="*60 + "\n")
        return new_key

    return key.encode()


# Initialize cipher with encryption key
_cipher = Fernet(get_encryption_key())


def encrypt_token(token: str) -> str:
    """
    Encrypt a token string

    Args:
        token: Plain text token

    Returns:
        str: Encrypted token (base64 encoded string)
    """
    if not token:
        return ""

    encrypted = _cipher.encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an encrypted token

    Args:
        encrypted_token: Encrypted token string

    Returns:
        str: Plain text token

    Raises:
        ValueError: If decryption fails (wrong key or corrupted data)
    """
    if not encrypted_token:
        return ""

    try:
        decrypted = _cipher.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt token. Wrong encryption key? Error: {str(e)}")


# =============================================================================
# Email Body Encryption (Data Lifecycle)
# =============================================================================

def encrypt_body(body: str) -> str:
    """
    Encrypt email body for storage at rest

    Args:
        body: Plain text email body

    Returns:
        str: Encrypted body (base64 encoded string)
    """
    if not body:
        return ""

    encrypted = _cipher.encrypt(body.encode())
    return encrypted.decode()


def decrypt_body(encrypted_body: str) -> str:
    """
    Decrypt an encrypted email body

    Args:
        encrypted_body: Encrypted body string

    Returns:
        str: Plain text email body

    Raises:
        ValueError: If decryption fails (wrong key or corrupted data)
    """
    if not encrypted_body:
        return ""

    try:
        decrypted = _cipher.decrypt(encrypted_body.encode())
        return decrypted.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt body. Wrong encryption key? Error: {str(e)}")
