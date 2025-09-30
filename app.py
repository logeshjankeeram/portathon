import os
import sys

# Ensure src layout is importable in container/runtime
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "mana", "src")
EXAMPLES_DIR = os.path.join(BASE_DIR, "mana")
for p in (SRC_DIR, EXAMPLES_DIR, BASE_DIR):
    if p not in sys.path:
        sys.path.append(p)

# Import FastAPI application
from mana.examples.live_server import app  # noqa: E402
