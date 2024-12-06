# setup_jwt_keys.py
import secrets
import os
from pathlib import Path

def setup_jwt_keys():
    """Set up JWT keys for both development and production environments"""
    
    # Generate a secure key
    fallback_key = secrets.token_hex(32)
    
    # Create dev_settings.py if it doesn't exist
    dev_settings_path = Path('dev_settings.py')
    if not dev_settings_path.exists():
        dev_settings_content = f'''# Development Settings
# WARNING: These settings are for development only!

DEV_JWT_SECRET_KEY = '{fallback_key}'

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
'''
        with open(dev_settings_path, 'w') as f:
            f.write(dev_settings_content)
        print("Created dev_settings.py with fallback key")
    
    # Set up .env file for production key
    env_path = Path('.env')
    if not env_path.exists():
        production_key = secrets.token_hex(32)
        with open(env_path, 'w') as f:
            f.write(f'JWT_SECRET_KEY={production_key}')
        print("Created .env file with production key")
    
    # Add dev_settings.py to .gitignore
    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        with open(gitignore_path, 'w') as f:
            f.write('dev_settings.py\n.env\n')
    else:
        with open(gitignore_path, 'r') as f:
            content = f.read()
        if 'dev_settings.py' not in content:
            with open(gitignore_path, 'a') as f:
                f.write('\ndev_settings.py\n')
    print("Updated .gitignore")

    print("\nSetup complete!")
    print("Remember:")
    print("1. Never commit dev_settings.py or .env to version control")
    print("2. Use different keys for development and production")
    print("3. In production, always set JWT_SECRET_KEY in environment variables")

if __name__ == '__main__':
    setup_jwt_keys()