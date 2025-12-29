import os

def get_version():
    """Reads the VERSION file from the project root."""
    # Assuming standard structure where common is at root/common
    # and VERSION is at root/VERSION
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        version_path = os.path.join(base_dir, 'VERSION')
        
        # Fallback: If installed as package, might need to look higher or rely on env
        if not os.path.exists(version_path):
            # Try Docker path /app/VERSION
            if os.path.exists("/app/VERSION"):
                version_path = "/app/VERSION"
            else:
                 return "Unknown (Dev)"
                 
        with open(version_path, 'r') as f:
            return f.read().strip()
    except Exception:
        return "Unknown (Error)"
