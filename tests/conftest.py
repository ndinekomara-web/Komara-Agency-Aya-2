"""Prépare un environnement isolé : base locale temporaire, pas de Google."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="aya-tests-")
os.environ.setdefault("MEMORY_DIR", _TMP)
os.environ.setdefault("RAG_BACKEND", "keyword")
os.environ.setdefault("APP_ACCESS_TOKEN", "")
os.environ.setdefault("GOOGLE_SHEETS_ID", "")
