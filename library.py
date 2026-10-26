"""Portable library persistence; original media is referenced, never modified."""
import json
import os
import uuid
from pathlib import Path

class Library:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'library.json'
        self.warning = ''
        self.data = dict(version=1, categories=['General', 'Effects', 'Music'], sounds=[],
                         settings=dict(preview='', broadcast='', mode='preview', volume=65, broadcast_volume=65, normalize=False))
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding='utf-8'))
                if loaded.get('version') != 1 or not isinstance(loaded.get('sounds'), list):
                    raise ValueError('Unsupported library format')
                if not all(isinstance(s, dict) and all(isinstance(s.get(k), str) for k in ['id','name','path','category']) for s in loaded['sounds']):
                    raise ValueError('Invalid sound entry')
                if not isinstance(loaded.get('categories'), list) or not all(isinstance(c, str) for c in loaded['categories']):
                    raise ValueError('Invalid category list')
                settings = self.data['settings']
                settings.update(loaded.get('settings', {}))
                loaded['settings'] = settings
                self.data = loaded
            except Exception as e:
                backup = self.path.with_name('library.unreadable-' + uuid.uuid4().hex[:8] + '.json')
                backup.write_bytes(self.path.read_bytes())
                self.warning = f'Could not read library; the original file was preserved as {backup.name}. {e}'

    def save(self):
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, self.path)

    @property
    def sounds(self): return self.data['sounds']

    def add(self, path, category='General'):
        path = str(Path(path).resolve())
        if any(s['path'].casefold() == path.casefold() for s in self.sounds): return None
        entry = dict(id=uuid.uuid4().hex, name=Path(path).stem, path=path, category=category,
                     hotkey='', favorite=False, duration=None, plays=0)
        self.sounds.append(entry)
        self.save()
        return entry

