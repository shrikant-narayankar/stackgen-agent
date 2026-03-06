import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

def get_available_users():
    """Dynamically parses .env to find all defined users.
    
    Expects keys in the format:
    USER<ID>_NAME=Bob
    GITHUB_USER<ID>_TOKEN=...
    GITHUB_USER<ID>_USERNAME=...
    LINEAR_USER<ID>_TOKEN=...
    
    Returns a dict mapping lowercase user names to their configs.
    """
    users = {}
    for key, value in os.environ.items():
        if key.startswith('USER') and key.endswith('_NAME'):
            # Extract ID from USER1_NAME
            user_id = key.split('_')[0][4:]
            if user_id:
                users[value.lower()] = {
                    'name': value,
                    'github_token': os.getenv(f'GITHUB_USER{user_id}_TOKEN'),
                    'github_username': os.getenv(f'GITHUB_USER{user_id}_USERNAME'),
                    'linear_token': os.getenv(f'LINEAR_USER{user_id}_TOKEN')
                }
    return users
