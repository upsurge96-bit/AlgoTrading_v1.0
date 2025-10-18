"""
Token Security
------------
Security utilities for token encryption, decryption and secure storage.
"""

import os
import json
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configure logging
from core.utils.logger import get_logger
logger = get_logger("token_security")

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


def generate_key(master_key=None):
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
    key = generate_key(master_key)
    
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
        key = generate_key(master_key)
        
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


def is_token_valid(token_data):
    """
    Check if token is valid based on expiry time.
    
    Args:
        token_data (dict): Token data to check
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    # datetime and timezone are imported at the top of file
    
    if not token_data or not isinstance(token_data, dict):
        return False
        
    # Check if token has expiry information
    expires_at = token_data.get("expires_at")
    if not expires_at:
        return False
        
    # Check if token is expired
    try:
        # Get current time in UTC
        current_time = datetime.now(timezone.utc).timestamp()
        
        # Convert expiry to timestamp if it's not already
        if isinstance(expires_at, str):
            try:
                # Try to parse ISO format
                expires_at = datetime.fromisoformat(expires_at).timestamp()
            except ValueError:
                # If fromisoformat fails, try strptime
                try:
                    expires_at = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S.%f").timestamp()
                except ValueError:
                    try:
                        expires_at = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S").timestamp()
                    except ValueError:
                        # If all parsing attempts fail, try float conversion directly
                        expires_at = float(expires_at)
        
        return current_time < expires_at
    except Exception as e:
        logger.error(f"Error checking token validity: {e}")
        return False


def get_token_expiry(token_data):
    """
    Get formatted token expiry information.
    
    Args:
        token_data (dict): Token data
        
    Returns:
        tuple: (timestamp, human_readable_string)
    """
    # datetime and timezone are imported at the top of file
    
    if not token_data or not isinstance(token_data, dict):
        return None, "No token data"
        
    expires_at = token_data.get("expires_at")
    if not expires_at:
        return None, "No expiry information"
        
    try:
        # Convert expiry to timestamp if it's not already
        if isinstance(expires_at, str):
            try:
                # Try to parse ISO format
                expires_at = datetime.fromisoformat(expires_at).timestamp()
            except ValueError:
                # If fromisoformat fails, try strptime
                try:
                    expires_at = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S.%f").timestamp()
                except ValueError:
                    try:
                        expires_at = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S").timestamp()
                    except ValueError:
                        # If all parsing attempts fail, try float conversion directly
                        expires_at = float(expires_at)
                        
        # Create a datetime object from the timestamp
        expiry_date = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        
        # Calculate time remaining
        now = datetime.now(timezone.utc)
        time_left = expiry_date - now
        
        if time_left.total_seconds() <= 0:
            return expires_at, "Expired"
            
        # Format human readable string
        hours, remainder = divmod(time_left.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            human_readable = f"{int(hours)}h {int(minutes)}m remaining"
        else:
            human_readable = f"{int(minutes)}m {int(seconds)}s remaining"
            
        return expires_at, human_readable
        
    except Exception as e:
        logger.error(f"Error formatting token expiry: {e}")
        return expires_at, "Error calculating expiry"