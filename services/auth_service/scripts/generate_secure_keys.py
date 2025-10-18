#!/usr/bin/env python3
"""
generate_secure_keys.py
----------------------
Helper script to generate secure random keys for production use.
"""

import os
import base64
import secrets
import string
from pathlib import Path

def generate_encryption_key():
    """Generate a secure random key for token encryption."""
    # Generate 32 random bytes and encode them as URL-safe base64
    random_bytes = os.urandom(32)
    return base64.urlsafe_b64encode(random_bytes).decode('utf-8')

def generate_api_key(length=32):
    """Generate a secure random API key."""
    # Use a mix of letters, digits, and some special characters
    alphabet = string.ascii_letters + string.digits + "_-"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    # Generate keys
    encryption_key = generate_encryption_key()
    admin_api_key = generate_api_key(40)  # Longer key for better security
    
    # Print the keys
    print("\n===== SECURE KEYS FOR PRODUCTION =====")
    print(f"\nTOKEN_ENCRYPTION_KEY={encryption_key}")
    print(f"\nADMIN_API_KEY={admin_api_key}")
    
    # Offer to save to a file
    save = input("\nSave these keys to .env.production? (y/n): ")
    if save.lower() == 'y':
        # Set the correct path relative to the script location
        # Handle the case when script is run from scripts/ directory
        script_dir = Path(__file__).resolve().parent
        service_dir = script_dir.parent
        
        # Env file should be at the service root
        env_file = service_dir / ".env.production"
        
        # If file exists, read it first to preserve other settings
        env_content = ""
        if env_file.exists():
            with open(env_file, 'r') as f:
                lines = f.readlines()
                # Remove existing keys if present
                lines = [line for line in lines if not (line.startswith('TOKEN_ENCRYPTION_KEY=') or line.startswith('ADMIN_API_KEY='))]
                env_content = ''.join(lines)
            
            if env_content and not env_content.endswith('\n'):
                env_content += '\n'
        
        # Add the new keys
        env_content += f"TOKEN_ENCRYPTION_KEY={encryption_key}\n"
        env_content += f"ADMIN_API_KEY={admin_api_key}\n"
        
        # Write to file
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print(f"\nKeys saved to {env_file.resolve()}")
        print("IMPORTANT: Keep this file secure and do not commit it to version control!")
    
    print("\nIMPORTANT: Store these keys securely. If lost, all encrypted tokens will be inaccessible.")

if __name__ == "__main__":
    main()