"""Fail-closed recovery of a marked native worker after its supervisor died."""
import os
from pathlib import Path
import psutil


def manifest(root, script):
    parent = psutil.Process()
    return {'parent_pid': parent.pid, 'parent_created': parent.create_time(),
            'executable': str((Path(root) / 'python32/python.exe').resolve()),
            'script': str(Path(script).resolve()), 'root': str(Path(root).resolve())}


def child_arguments(record, run_id, instance):
    return [record['executable'], record['script'], record['root'],
            '--hub-run', run_id, '--hub-instance', instance]


def recover(record, run_id, instance, expected):
    # Stored paths are evidence, never arbitrary administrator-supplied kill targets.
    if any(record.get(key) != expected[key] for key in ('executable', 'script', 'root')):
        raise ValueError('Installierter Worker und Wiederanlaufbeleg stimmen nicht überein.')
    try:
        parent = psutil.Process(record['parent_pid'])
        if parent.create_time() == record['parent_created'] and parent.is_running():
            raise ValueError('Die ursprüngliche Serverinstanz läuft noch.')
    except psutil.NoSuchProcess:
        pass
    command = child_arguments(record, run_id, instance)
    # Refresh the process cache: PID reuse must not retain a prior command line.
    psutil.process_iter.cache_clear()
    for process in psutil.process_iter():
        try:
            if process.name().lower() != Path(record['executable']).name.lower(): continue
            args = process.cmdline()
            if '--hub-run' not in args or run_id not in args: continue
            if args != command or os.path.normcase(process.exe()) != os.path.normcase(record['executable']):
                raise ValueError('Worker-Identität ist mehrdeutig; keine Freigabe.')
            # psutil kill checks PID plus process creation time before signaling.
            process.kill()
            process.wait(timeout=5)
        except psutil.NoSuchProcess:
            continue
        # AccessDenied and TimeoutExpired deliberately propagate: no proven stop.
    return True
