"""Fetch pinned upstream binaries/data into ignored artifacts, never into the Hub DB.

Run with the project's 64-bit .venv Python. No installer or system changes.
The lock contains exact URLs and SHA-256, not floating branches.
"""
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import httpx

BASE = Path(__file__).resolve().parent
DEFAULT_ROOT = BASE.parents[1] / 'artifacts' / 'duel-probe'


def provision(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = json.loads((BASE / 'sources.lock.json').read_text(encoding='utf8'))
    files = {}
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        for source in lock['sources']:
            response = client.get(source['url']); response.raise_for_status()
            blob = response.content
            if hashlib.sha256(blob).hexdigest() != source['sha256']:
                raise ValueError('Source checksum mismatch: ' + source['name'])
            if source.get('archive'):
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    if sum(item.file_size for item in archive.infolist()) > 200_000_000:
                        raise ValueError('Archive limit exceeded')
                    for item in archive.infolist():
                        if item.is_dir(): continue
                        parts = Path(item.filename).parts[source.get('strip', 0):]
                        target = root / source['target'] / Path(*parts)
                        target = target.resolve()
                        if not target.is_relative_to(root): raise ValueError('Unsafe archive path')
                        data = archive.read(item)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        files[target.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
            else:
                target = root / source['target']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob)
                files[target.relative_to(root).as_posix()] = source['sha256']
            print('Prepared: ' + source['name'], flush=True)
        strings = json.loads((BASE / 'strings.lock.json').read_text(encoding='utf8'))
        response = client.get(strings['url']); response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != strings['sha256']: raise ValueError('System strings checksum mismatch')
        path = root / 'config/strings.conf'; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(response.content)
        files['config/strings.conf'] = strings['sha256']
    (root / 'verified-files.json').write_text(json.dumps(files, indent=2), encoding='utf8')
    return root


def verify(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    hashes = json.loads((root / 'verified-files.json').read_text(encoding='utf8'))
    checked_directories = set()
    for name, digest in hashes.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe runtime manifest path: ' + name)
        path = root / relative
        if path.parent not in checked_directories:
            if not path.parent.resolve().is_relative_to(root): raise ValueError('Unsafe runtime manifest directory: ' + name)
            checked_directories.add(path.parent)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Runtime was modified: ' + name)


if __name__ == '__main__':
    if '--verify' in sys.argv:
        verify(); print('Runtime files verified.')
    else:
        provision()
