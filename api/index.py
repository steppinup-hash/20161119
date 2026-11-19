import os
import sys

# Add project root directory to sys.path so backend modules can be imported in Vercel
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.server import AppRequestHandler
from backend.storage import init_db

# Initialize database in Vercel /tmp on function boot
init_db()

# Vercel entrypoint
handler = AppRequestHandler
