"""Exercise Windows starter recovery with fake network/processes, never production."""
import os
from pathlib import Path
import subprocess
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell starter')
class PublicStarterRetryTests(unittest.TestCase):
    def test_retry_recovery_and_permanent_failure_boundaries(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             str(root / 'scripts/tests/public-test-retry-checks.ps1')],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PUBLIC_TEST_RETRY_CHECKS_PASSED', result.stdout)
        self.assertNotIn('SECRET-MUST-NOT-LEAK', result.stdout + result.stderr)
