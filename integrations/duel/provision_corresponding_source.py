"""Prepare pinned matching core/Lua source and preserved licenses. No compilation."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def prepare(output=None):
    output = Path(output or ROOT / 'artifacts/duel-corresponding-source').resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = json.loads((HERE / 'corresponding-source.lock.json').read_text(encoding='utf8'))
    files = {}
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for source in lock['sources']:
            response = client.get(source['url']); response.raise_for_status()
            blob = response.content
            if hashlib.sha256(blob).hexdigest() != source['sha256']: raise ValueError('Source archive checksum mismatch')
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                if sum(row.file_size for row in archive.infolist()) > 100_000_000: raise ValueError('Source archive limit')
                for item in archive.infolist():
                    if item.is_dir(): continue
                    target = (output / source['target'] / Path(*Path(item.filename).parts[1:])).resolve()
                    if not target.is_relative_to(output): raise ValueError('Unsafe archive path')
                    data = archive.read(item); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
                    files[target.relative_to(output).as_posix()] = hashlib.sha256(data).hexdigest()
    (output / 'provenance.json').write_text(json.dumps({**lock, 'files': files, 'local_rebuild_performed': False}, indent=2), encoding='utf8')
    print(json.dumps({'status': 'prepared', 'source_files': len(files), 'path': str(output), 'local_rebuild_performed': False}))


if __name__ == '__main__': prepare()
