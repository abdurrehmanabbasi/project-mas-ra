"""Streamlit application root entrypoint."""

from pathlib import Path
import sys

# Ensure repository root is in sys.path
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Delegate directly to dashboard implementation
import streamlit_app.app

