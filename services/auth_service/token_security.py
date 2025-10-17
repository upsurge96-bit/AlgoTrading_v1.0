#!/usr/bin/env python3
"""
token_security.py
----------------
Security utilities for token encryption, decryption and secure storage.
"""

import os
import json
import base64
import logging
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token_security")

# Constants
ENCRYPTION_KEY_FILE = Path("data/encryption.key")
TOKEN_FILE = Path("data/kite_access_token.enc")
SALT_FILE = Path("data/salt.bin")


def ensure_data_directory():
    """Ensure the data directory exists with proper permissions."""
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir(mode=0o700)  # Only owner can read/write/execute
    elif os.name != 'nt':  # Skip on Windows
        # Ensure proper permissions on existing directory
        os.chmod(data_dir, 0o700)
    return data_dir


def generate_encryption_key(master_key=None):
    """
    Generate an encryption key from a master key or generate a new random one.
    
    Args:
        master_key (str): Optional master key to derive encryption key
    
    Returns:
        bytes: The encryption key
    """
    ensure_data_directory()
    
    # If master key is provided, derive a key from it
    if master_key:
        # Generate or load a persistent salt
        if not SALT_FILE.exists():
            salt = os.urandom(16)
            SALT_FILE.write_bytes(salt)
            # Set restricted permissions on Windows
            if os.name != 'nt':
                os.chmod(SALT_FILE, 0o600)
        else:
            salt = SALT_FILE.read_bytes()
        
        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
    else:
        # Generate a random key if no master key provided
        if ENCRYPTION_KEY_FILE.exists():
            key = ENCRYPTION_KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            ENCRYPTION_KEY_FILE.write_bytes(key)
            # Set restricted permissions
            if os.name != 'nt':
                os.chmod(ENCRYPTION_KEY_FILE, 0o600)
    
    return key


def encrypt_token(token_data, master_key=None):
    """
    Encrypt token data and save to file.
    
    Args:
        token_data (dict): Token data to encrypt
        master_key (str): Optional master key to derive encryption key
    """
    ensure_data_directory()
    
    # Convert token data to JSON
    token_json = json.dumps(token_data).encode()
    
    # Get encryption key
    key = generate_encryption_key(master_key)
    
    # Encrypt the token
    fernet = Fernet(key)
    encrypted_token = fernet.encrypt(token_json)
    
    # Save to file with restricted permissions
    TOKEN_FILE.write_bytes(encrypted_token)
    if os.name != 'nt':  # Skip on Windows
        os.chmod(TOKEN_FILE, 0o600)
    
    logger.info(f"Token encrypted and saved to {TOKEN_FILE}")


def decrypt_token(master_key=None):
    """
    Decrypt token from file.
    
    Args:
        master_key (str): Optional master key to derive encryption key
    
    Returns:
        dict: Decrypted token data or None if decryption fails
    """
    if not TOKEN_FILE.exists():
        logger.warning(f"Token file not found at {TOKEN_FILE}")
        return None
    
    try:
        # Read encrypted token
        encrypted_token = TOKEN_FILE.read_bytes()
        
        # Get encryption key
        key = generate_encryption_key(master_key)
        
        # Decrypt the token
        fernet = Fernet(key)
        decrypted_token = fernet.decrypt(encrypted_token)
        
        # Parse JSON
        token_data = json.loads(decrypted_token.decode())
        return token_data
    
    except (InvalidToken, json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to decrypt token: {str(e)}")
        return None


def secure_save_token(token_data, master_key=None):
    """
    Securely save token data to file.
    
    Args:
        token_data (dict): Token data to save
        master_key (str): Optional master key to derive encryption key
    """
    encrypt_token(token_data, master_key)


def secure_load_token(master_key=None):
    """
    Securely load token data from file.
    
    Args:
        master_key (str): Optional master key to derive encryption key
    
    Returns:
        dict: Decrypted token data or None if loading fails
    """
    return decrypt_token(master_key)