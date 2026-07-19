import base64
from flask import current_app

def encrypt_value(value: str) -> str:
    """Encrypt a string value using XOR cipher and application SECRET_KEY, base64 encoded.
    
    If the value is empty, returns empty string.
    """
    if not value:
        return ""
    key = current_app.config.get("SECRET_KEY", "fallback-key")
    key_bytes = key.encode('utf-8')
    val_bytes = value.encode('utf-8')
    encrypted = bytes(val_bytes[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(val_bytes)))
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_value(value: str) -> str:
    """Decrypt a base64 encoded XOR encrypted string using application SECRET_KEY.
    
    If decryption fails or value is not base64 encoded, returns the value as-is
    for backward compatibility with plaintext values in the database.
    """
    if not value:
        return ""
    key = current_app.config.get("SECRET_KEY", "fallback-key")
    try:
        # Check if it looks like base64 first to avoid printing traceback in try block
        # base64 length is always a multiple of 4 (with padding)
        if len(value) % 4 != 0:
            return value
        
        # Test if characters are valid base64 alphabet
        # A-Z, a-z, 0-9, +, /, =
        import re
        if not re.match(r'^[A-Za-z0-9+/=]+$', value):
            return value

        encrypted_bytes = base64.b64decode(value.encode('utf-8'))
        key_bytes = key.encode('utf-8')
        decrypted = bytes(encrypted_bytes[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(encrypted_bytes)))
        return decrypted.decode('utf-8')
    except Exception:
        # Fallback to plaintext for backward compatibility
        return value
