import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import process_identity as identity


class ProcessIdentityTests(unittest.TestCase):
    def setUp(self):
        self.record = {'parent_pid': 123, 'parent_created': 10.0,
            'executable': str(Path('test-python/python.exe').resolve()),
            'script': str(Path('test-worker.py').resolve()), 'root': str(Path('test-root').resolve())}

    def test_live_original_supervisor_cannot_be_recovered(self):
        parent = Mock(); parent.create_time.return_value = 10.0; parent.is_running.return_value = True
        with patch.object(identity.psutil, 'Process', return_value=parent), patch.object(identity.psutil, 'process_iter') as processes:
            with self.assertRaises(ValueError): identity.recover(self.record, 'run', 'instance', self.record)
            processes.assert_not_called()

    def test_pid_reuse_only_stops_exact_marked_child_and_waits(self):
        parent = Mock(); parent.create_time.return_value = 20.0
        child = Mock(); child.name.return_value = 'python.exe'
        child.cmdline.return_value = identity.child_arguments(self.record, 'run', 'instance')
        child.exe.return_value = self.record['executable']
        unrelated = Mock(); unrelated.name.return_value = 'python.exe'; unrelated.cmdline.return_value = ['python.exe', 'other.py']
        with patch.object(identity.psutil, 'Process', return_value=parent), patch.object(identity.psutil, 'process_iter', return_value=[unrelated, child]):
            self.assertTrue(identity.recover(self.record, 'run', 'instance', self.record))
        child.kill.assert_called_once(); child.wait.assert_called_once_with(timeout=5)
        unrelated.kill.assert_not_called()

    def test_wrong_command_or_stop_timeout_never_proves_release(self):
        parent = Mock(); parent.create_time.return_value = 20.0
        child = Mock(); child.name.return_value = 'python.exe'
        child.cmdline.return_value = ['python.exe', '--hub-run', 'run']
        with patch.object(identity.psutil, 'Process', return_value=parent), patch.object(identity.psutil, 'process_iter', return_value=[child]):
            with self.assertRaises(ValueError): identity.recover(self.record, 'run', 'instance', self.record)
            child.kill.assert_not_called()
            child.cmdline.return_value = identity.child_arguments(self.record, 'run', 'instance')
            child.exe.return_value = self.record['executable']
            child.wait.side_effect = identity.psutil.TimeoutExpired(5)
            with self.assertRaises(identity.psutil.TimeoutExpired): identity.recover(self.record, 'run', 'instance', self.record)

    def test_missing_supervisor_and_no_matching_child_are_confirmed(self):
        with patch.object(identity.psutil, 'Process', side_effect=identity.psutil.NoSuchProcess(123)), patch.object(identity.psutil, 'process_iter', return_value=[]):
            self.assertTrue(identity.recover(self.record, 'run', 'instance', self.record))
        with self.assertRaises(ValueError): identity.recover(self.record, 'run', 'instance', {**self.record, 'root': 'different'})
