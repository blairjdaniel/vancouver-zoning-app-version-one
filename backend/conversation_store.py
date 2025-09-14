import os
import json
import time
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'conversations')

def _ensure_dir():
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)


def _sanitize_filename(s: str) -> str:
    # Basic sanitization for filenames
    return ''.join(c for c in s if c.isalnum() or c in (' ', '-', '_')).rstrip()


def save_conversation(data: Dict[str, Any], filename: Optional[str] = None) -> str:
    """Save a conversation dict to a timestamped JSON file. Returns the filepath."""
    _ensure_dir()
    ts = int(time.time())
    if filename:
        base = _sanitize_filename(filename)
        fname = f"{base}_{ts}.json"
    else:
        fname = f"conversation_{ts}.json"
    path = os.path.join(BASE_DIR, fname)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def list_conversations(limit: int = 50) -> List[str]:
    _ensure_dir()
    files = [f for f in os.listdir(BASE_DIR) if f.endswith('.json')]
    files_sorted = sorted(files, reverse=True)
    return files_sorted[:limit]


def load_conversation(filename: str) -> Dict[str, Any]:
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
