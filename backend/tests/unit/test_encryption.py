"""
Unit Tests for Encryption Module (app/encryption.py)

=== WHAT DOES encryption.py DO? ===
Handles encryption of sensitive data stored in the database:
- OAuth tokens (Gmail/Calendar credentials)
- Email body content (privacy protection)

Uses Fernet symmetric encryption (AES-128 + HMAC).

=== WHY IS THIS CRITICAL? ===
- Wrong encryption = users locked out of their Gmail
- Lost keys = all stored tokens become useless
- Decryption failures = emails unreadable

Run tests with: pytest tests/unit/test_encryption.py -v
"""
import pytest
from unittest.mock import patch, MagicMock


# -----------------------------------------------------------------------------
# SETUP: Import encryption functions
# -----------------------------------------------------------------------------
# We need to mock the settings before importing, since encryption.py
# initializes the cipher at module load time.

@pytest.fixture(autouse=True)
def mock_encryption_key():
    """
    Provide a test encryption key for all tests.
    This prevents the module from generating a new key each time.
    """
    # Valid Fernet key (32 url-safe base64-encoded bytes)
    test_key = "dGVzdF9lbmNyeXB0aW9uX2tleV8zMl9ieXRlcyE="
    
    with patch("app.encryption.settings") as mock_settings:
        mock_settings.ENCRYPTION_KEY = test_key
        # Need to reimport to apply the mocked key
        import importlib
        import app.encryption
        importlib.reload(app.encryption)
        yield test_key


# =============================================================================
# TEST: Token Encryption (OAuth credentials)
# =============================================================================

class TestTokenEncryption:
    """
    Tests for encrypting/decrypting OAuth tokens.
    
    Tokens are sensitive credentials that allow access to a user's Gmail.
    They must be stored encrypted and decrypted correctly on retrieval.
    """
    
    @pytest.mark.unit
    def test_encrypted_token_can_be_decrypted_back(self):
        """
        WHAT: Encrypting then decrypting a token should return the original.
        WHY: This is the fundamental requirement - we must be able to retrieve credentials.
        """
        from app.encryption import encrypt_token, decrypt_token
        
        original_token = "ya29.a0AfH6SMBx..."  # Fake OAuth token
        
        # Encrypt -> Decrypt should give us back the original
        encrypted = encrypt_token(original_token)
        decrypted = decrypt_token(encrypted)
        
        assert decrypted == original_token
    
    @pytest.mark.unit
    def test_encrypted_token_looks_different_from_original(self):
        """
        WHAT: The encrypted version should not be readable.
        WHY: If encrypted text == original text, encryption isn't working.
        """
        from app.encryption import encrypt_token
        
        original_token = "super_secret_refresh_token_abc123"
        encrypted = encrypt_token(original_token)
        
        # Encrypted text should be different from original
        assert encrypted != original_token
        
        # Original token should not appear in encrypted output
        assert original_token not in encrypted
    
    @pytest.mark.unit
    def test_empty_token_returns_empty_string(self):
        """
        WHAT: Empty string input should return empty string output.
        WHY: Handle edge case gracefully instead of throwing errors.
        """
        from app.encryption import encrypt_token, decrypt_token
        
        assert encrypt_token("") == ""
        assert decrypt_token("") == ""
    
    @pytest.mark.unit
    def test_same_token_encrypts_differently_each_time(self):
        """
        WHAT: Encrypting the same token twice should produce different ciphertext.
        WHY: Fernet includes a random IV, so same input = different output (good for security).
        """
        from app.encryption import encrypt_token
        
        token = "my_oauth_access_token"
        
        encrypted_1 = encrypt_token(token)
        encrypted_2 = encrypt_token(token)
        
        # Both should be different (random IV each time)
        assert encrypted_1 != encrypted_2
    
    @pytest.mark.unit
    def test_long_token_encrypts_correctly(self):
        """
        WHAT: Very long tokens should encrypt and decrypt correctly.
        WHY: Refresh tokens can be quite long - make sure no truncation.
        """
        from app.encryption import encrypt_token, decrypt_token
        
        # Simulate a long refresh token (they can be 200+ characters)
        long_token = "1//0g" + "x" * 200 + "_very_long_token"
        
        encrypted = encrypt_token(long_token)
        decrypted = decrypt_token(encrypted)
        
        assert decrypted == long_token
        assert len(decrypted) == len(long_token)


# =============================================================================
# TEST: Email Body Encryption (Privacy)
# =============================================================================

class TestEmailBodyEncryption:
    """
    Tests for encrypting/decrypting email body content.
    
    Email bodies are encrypted at rest to protect user privacy.
    Only decrypted when needed for display or AI processing.
    """
    
    @pytest.mark.unit
    def test_encrypted_body_can_be_decrypted_back(self):
        """
        WHAT: Encrypting then decrypting an email body should return the original.
        WHY: Users need to see their emails after they're stored.
        """
        from app.encryption import encrypt_body, decrypt_body
        
        original_body = """
        Hi John,
        
        Just following up on our meeting yesterday. 
        Please review the attached proposal by Friday.
        
        Best,
        Sarah
        """
        
        encrypted = encrypt_body(original_body)
        decrypted = decrypt_body(encrypted)
        
        assert decrypted == original_body
    
    @pytest.mark.unit
    def test_encrypted_body_hides_content(self):
        """
        WHAT: Encrypted email should not contain readable content.
        WHY: Someone with database access shouldn't be able to read emails.
        """
        from app.encryption import encrypt_body
        
        sensitive_email = """
        CONFIDENTIAL: Q4 earnings will be announced on Friday.
        Do not share this information until the official release.
        """
        
        encrypted = encrypt_body(sensitive_email)
        
        # None of the sensitive content should be visible
        assert "CONFIDENTIAL" not in encrypted
        assert "Q4 earnings" not in encrypted
        assert "Friday" not in encrypted
    
    @pytest.mark.unit
    def test_empty_body_returns_empty_string(self):
        """
        WHAT: Empty email body should return empty string.
        WHY: Some emails have empty bodies (subject-only) - handle gracefully.
        """
        from app.encryption import encrypt_body, decrypt_body
        
        assert encrypt_body("") == ""
        assert decrypt_body("") == ""
    
    @pytest.mark.unit
    def test_unicode_email_body_encrypts_correctly(self):
        """
        WHAT: Emails with unicode characters (emoji, non-ASCII) should work.
        WHY: Real emails contain emojis, accents, CJK characters, etc.
        """
        from app.encryption import encrypt_body, decrypt_body
        
        unicode_email = """
        Bonjour François! 🇫🇷
        
        明天见！(See you tomorrow!)
        
        Спасибо за помощь 🙏
        """
        
        encrypted = encrypt_body(unicode_email)
        decrypted = decrypt_body(encrypted)
        
        assert decrypted == unicode_email
    
    @pytest.mark.unit
    def test_large_email_body_encrypts_correctly(self):
        """
        WHAT: Very large emails should encrypt and decrypt without issues.
        WHY: Some emails have long threads or large HTML content.
        """
        from app.encryption import encrypt_body, decrypt_body
        
        # Simulate a large email (50KB of text)
        large_body = "This is a line of email content.\n" * 1500
        
        encrypted = encrypt_body(large_body)
        decrypted = decrypt_body(encrypted)
        
        assert decrypted == large_body
        assert len(decrypted) == len(large_body)


# =============================================================================
# TEST: Decryption Failures (Security Edge Cases)
# =============================================================================

class TestDecryptionErrors:
    """
    Tests for error handling when decryption fails.
    
    These scenarios can happen if:
    - Encryption key changed (app redeployed with new key)
    - Data corrupted in database
    - Someone tampered with encrypted data
    """
    
    @pytest.mark.unit
    def test_corrupted_token_raises_error(self):
        """
        WHAT: Attempting to decrypt garbage data should raise ValueError.
        WHY: Clear error is better than silent failure with wrong data.
        """
        from app.encryption import decrypt_token
        
        corrupted_data = "this_is_not_valid_encrypted_data"
        
        with pytest.raises(ValueError) as exc_info:
            decrypt_token(corrupted_data)
        
        assert "Failed to decrypt" in str(exc_info.value)
    
    @pytest.mark.unit
    def test_corrupted_body_raises_error(self):
        """
        WHAT: Attempting to decrypt corrupted email body should raise ValueError.
        WHY: Better to show error than display garbage content.
        """
        from app.encryption import decrypt_body
        
        corrupted_data = "definitely_not_valid_ciphertext!!!"
        
        with pytest.raises(ValueError) as exc_info:
            decrypt_body(corrupted_data)
        
        assert "Failed to decrypt" in str(exc_info.value)
    
    @pytest.mark.unit
    def test_tampered_data_is_detected(self):
        """
        WHAT: Modifying encrypted data should cause decryption to fail.
        WHY: Fernet includes HMAC authentication - tampering is detected.
        """
        from app.encryption import encrypt_token, decrypt_token
        
        original = "my_secret_token"
        encrypted = encrypt_token(original)
        
        # Tamper with the encrypted data (flip a character)
        tampered = encrypted[:-5] + "XXXXX"
        
        with pytest.raises(ValueError):
            decrypt_token(tampered)


# =============================================================================
# TEST: Encryption Key Handling
# =============================================================================

class TestEncryptionKeyHandling:
    """
    Tests for encryption key management.
    
    The encryption key is critical - if lost, all stored tokens are useless.
    """
    
    @pytest.mark.unit
    def test_missing_key_generates_valid_fernet_key(self):
        """
        WHAT: If ENCRYPTION_KEY is not set, a valid Fernet key is generated.
        WHY: Allow first-time setup to work, even if key isn't configured yet.
        """
        from cryptography.fernet import Fernet
        
        with patch("app.config.settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = None  # Simulate missing key
            
            # Import the function directly to test it
            import importlib
            import app.encryption
            
            # Force reload to trigger key generation path
            # Note: In production, user would see a warning printed
            importlib.reload(app.encryption)
            
            # The generated key should be usable for encryption
            # (get_encryption_key returns bytes suitable for Fernet)
            key = app.encryption.get_encryption_key()
            
            # Should be able to create a valid Fernet cipher with it
            cipher = Fernet(key)
            test_data = b"test_token"
            encrypted = cipher.encrypt(test_data)
            decrypted = cipher.decrypt(encrypted)
            
            assert decrypted == test_data
    
    @pytest.mark.unit
    def test_data_encrypted_with_different_key_cannot_be_decrypted(self):
        """
        WHAT: Data encrypted with key A cannot be decrypted with key B.
        WHY: This is why losing the key is so dangerous - data becomes unrecoverable.
        """
        from cryptography.fernet import Fernet
        
        # Create two different keys
        key_a = Fernet.generate_key()
        key_b = Fernet.generate_key()
        
        cipher_a = Fernet(key_a)
        cipher_b = Fernet(key_b)
        
        # Encrypt with key A
        secret = b"my_oauth_token"
        encrypted_with_a = cipher_a.encrypt(secret)
        
        # Try to decrypt with key B - should fail
        with pytest.raises(Exception):  # Fernet raises InvalidToken
            cipher_b.decrypt(encrypted_with_a)
