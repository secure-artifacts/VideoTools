"""
audio_library.py
Persistent audio library manager — stores audio entries as JSON on disk.
Entry format:
  {
    "name":       str   (display name, default = filename without extension),
    "path":       str   (absolute path),
    "skip_start": float (seconds to skip at the start, default 0.0),
    "fade_in":    float (fade-in duration in seconds, default 0.5),
  }
"""

import json
import os
import sys


SUPPORTED_AUDIO_EXT = ('.mp3', '.wav', '.aac', '.ogg')


def _get_library_path() -> str:
    """Resolve audio_library.json at the project root."""
    if getattr(sys, 'frozen', False):
        root = os.path.dirname(sys.executable)
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "audio_library.json")


class AudioLibrary:
    """JSON-backed audio library with per-entry skip/fade parameters."""

    def __init__(self):
        self._library_path = _get_library_path()
        self._items: list[dict] = []
        self.load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def load(self):
        if os.path.exists(self._library_path):
            try:
                with open(self._library_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._items = [
                        item for item in data
                        if isinstance(item, dict)
                        and 'name' in item and 'path' in item
                    ]
            except Exception:
                self._items = []
        else:
            self._items = []

        # Ensure all entries have the new fields (backward compat)
        for item in self._items:
            item.setdefault('skip_start', 0.0)
            item.setdefault('fade_in', 0.5)

    def save(self):
        try:
            with open(self._library_path, 'w', encoding='utf-8') as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AudioLibrary] Save failed: {e}")

    # ------------------------------------------------------------------ #
    #  CRUD                                                                #
    # ------------------------------------------------------------------ #

    def add(self, path: str) -> bool:
        """Add audio file. Returns True if added, False if duplicate."""
        path = os.path.normpath(path)
        for item in self._items:
            if os.path.normpath(item['path']) == path:
                return False
        name = os.path.splitext(os.path.basename(path))[0]
        self._items.append({
            'name':       name,
            'path':       path,
            'skip_start': 0.0,
            'fade_in':    0.5,
        })
        self.save()
        return True

    def remove(self, path: str):
        path = os.path.normpath(path)
        self._items = [i for i in self._items if os.path.normpath(i['path']) != path]
        self.save()

    def rename(self, path: str, new_name: str) -> bool:
        path = os.path.normpath(path)
        for item in self._items:
            if os.path.normpath(item['path']) == path:
                item['name'] = new_name.strip()
                self.save()
                return True
        return False

    def set_audio_params(self, path: str, skip_start: float, fade_in: float) -> bool:
        """Save per-audio skip_start and fade_in values."""
        path = os.path.normpath(path)
        for item in self._items:
            if os.path.normpath(item['path']) == path:
                item['skip_start'] = max(0.0, float(skip_start))
                item['fade_in']    = max(0.0, float(fade_in))
                self.save()
                return True
        return False

    def clear(self):
        self._items = []
        self.save()

    # ------------------------------------------------------------------ #
    #  Queries                                                             #
    # ------------------------------------------------------------------ #

    def get_all(self) -> list[dict]:
        return list(self._items)

    def get_name_for_path(self, path: str) -> str:
        path = os.path.normpath(path)
        for item in self._items:
            if os.path.normpath(item['path']) == path:
                return item['name']
        return os.path.splitext(os.path.basename(path))[0]

    def get_params_for_path(self, path: str) -> dict:
        """Return {'skip_start': float, 'fade_in': float} for a given path."""
        path = os.path.normpath(path)
        for item in self._items:
            if os.path.normpath(item['path']) == path:
                return {
                    'skip_start': item.get('skip_start', 0.0),
                    'fade_in':    item.get('fade_in',    0.5),
                }
        return {'skip_start': 0.0, 'fade_in': 0.5}
