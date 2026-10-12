import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verified_runtime', Path(__file__).resolve().parents[1] / 'provision.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class RuntimeIntegrityTests(unittest.TestCase):
    def test_nested_valid_files_and_modified_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'scripts').mkdir()
            file = root / 'scripts/card.lua'; file.write_bytes(b'original')
            (root / 'verified-files.json').write_text(json.dumps({'scripts/card.lua': hashlib.sha256(b'original').hexdigest()}))
            module.verify(root)
            file.write_bytes(b'changed')
            with self.assertRaises(ValueError): module.verify(root)

    def test_manifest_cannot_read_outside_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'runtime'; root.mkdir()
            sentinel = Path(directory) / 'private.txt'; sentinel.write_bytes(b'private')
            for name in ('../private.txt', str(sentinel.resolve())):
                (root / 'verified-files.json').write_text(json.dumps({name: hashlib.sha256(b'private').hexdigest()}))
                with self.assertRaises(ValueError): module.verify(root)
