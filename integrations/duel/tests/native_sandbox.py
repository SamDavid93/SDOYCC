"""Real Windows security probes, using disposable sentinels rather than Hub secrets."""
import asyncio
import ctypes as C
from ctypes import wintypes as W
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
from uuid import uuid4
import psutil

HERE = Path(__file__).resolve().parents[1]

PROBE = '''import ctypes as C, json, os, socket, subprocess, sys
from pathlib import Path
from ctypes import wintypes as W
kernel = C.WinDLL('kernel32', use_last_error=True)
advapi = C.WinDLL('advapi32', use_last_error=True)
kernel.GetCurrentProcess.restype = W.HANDLE
advapi.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
advapi.GetTokenInformation.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]
token = W.HANDLE(); flag = W.DWORD(); size = W.DWORD()
assert advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, C.byref(token))
assert advapi.GetTokenInformation(token, 29, C.byref(flag), C.sizeof(flag), C.byref(size))
report = {'appcontainer_token': flag.value == 1, 'server_environment_removed': 'DUEL_PARENT_SECRET_PROBE' not in os.environ}
advapi.GetTokenInformation(token, 30, None, 0, C.byref(size))
capabilities = C.create_string_buffer(size.value)
assert advapi.GetTokenInformation(token, 30, capabilities, size.value, C.byref(size))
report['no_capabilities'] = C.cast(capabilities, C.POINTER(W.DWORD))[0] == 0
try:
    Path(SENTINEL).read_bytes()
    report['outside_read_denied'] = False
except PermissionError:
    report['outside_read_denied'] = True
try:
    (Path(sys.argv[1]) / 'worker/forbidden-write').write_text('probe')
    report['runtime_write_denied'] = False
except PermissionError:
    report['runtime_write_denied'] = True
for name, address in [('loopback_network_denied', ('127.0.0.1', PORT)), ('internet_network_denied', ('1.1.1.1', 443))]:
    sock = socket.socket(); sock.settimeout(2)
    try:
        sock.connect(address); report[name] = False
    except OSError as error:
        report[name] = error.winerror == 10013 if name == 'internet_network_denied' else (
            error.winerror in (10013, 10060, 10061) or isinstance(error, TimeoutError))
    finally:
        sock.close()
try:
    process = subprocess.Popen([sys.executable, '-c', 'print(1)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    process.wait(timeout=3); report['child_process_denied'] = False
except PermissionError:
    report['child_process_denied'] = True
print(json.dumps(report), flush=True)
'''


async def run():
    spec = importlib.util.spec_from_file_location('native_sandbox', HERE / 'windows_sandbox.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    sandbox = module.Sandbox(HERE.parents[1] / 'artifacts/duel-probe', HERE / 'core_worker.py')
    with tempfile.TemporaryDirectory(prefix='sdoycc-sandbox-probe-') as temporary:
        sentinel = Path(temporary) / 'outside.txt'; sentinel.write_text('disposable-private-sentinel')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen()
            with socket.create_connection(listener.getsockname(), timeout=2):
                baseline, _ = listener.accept(); baseline.close()
            script = sandbox.script.parent / 'sandbox-probe.py'
            script.write_text('SENTINEL=' + repr(str(sentinel)) + '\nPORT=' + str(listener.getsockname()[1]) + '\n' + PROBE)
            previous = os.environ.get('DUEL_PARENT_SECRET_PROBE')
            os.environ['DUEL_PARENT_SECRET_PROBE'] = 'disposable-not-a-real-secret'
            process = None
            try:
                process = sandbox.launch([], script)
                report = json.loads(await asyncio.wait_for(process.stdout.readline(), 15))
                await process.wait(); process = None
                assert all(report.values()), report
                listener.settimeout(0.1)
                try:
                    connection, _ = listener.accept(); connection.close()
                    raise AssertionError('Sandbox reached host loopback listener')
                except TimeoutError:
                    pass
                assert sentinel.read_text() == 'disposable-private-sentinel'
                assert not (sandbox.root / 'worker/forbidden-write').exists()
            finally:
                if process:
                    if process.returncode is None: process.kill()
                    await process.wait()
                script.unlink(missing_ok=True)
                if previous is None: os.environ.pop('DUEL_PARENT_SECRET_PROBE', None)
                else: os.environ['DUEL_PARENT_SECRET_PROBE'] = previous
    # Run the actual pinned DLL and card database in a separately marked child.
    process = sandbox.launch([])
    try:
        process.stdin.write(b'{"op":"version"}\n'); await process.stdin.drain()
        version = json.loads(await asyncio.wait_for(process.stdout.readline(), 10))
        assert version == {'version': [11, 0]}, version
        report['native_core_api_11'] = True
    finally:
        if process.returncode is None: process.kill()
        await process.wait()
    # Fail after real CreateProcess, before the initial thread is resumed.
    original_job = sandbox.job_type
    for reason in ('assignment', 'resume'):
        marker = str(uuid4())
        class FailingJob(original_job):
            def __init__(self, pid):
                if reason == 'assignment': raise RuntimeError('injected assignment failure')
                super().__init__(pid)
            def resume(self, pid): raise RuntimeError('injected resume failure')
        sandbox.job_type = FailingJob
        try:
            sandbox.launch(['--hub-run', marker, '--hub-instance', marker])
            raise AssertionError('Injected sandbox failure did not propagate')
        except RuntimeError as error:
            assert 'injected' in str(error), error
        finally:
            sandbox.job_type = original_job
        assert not any(marker in process.cmdline() for process in psutil.process_iter()
            if process.name().lower() == 'python.exe')
        report[reason + '_failure_stops_child'] = True
    spec = importlib.util.spec_from_file_location('sandbox_engine', HERE / 'engine_process.py')
    engine_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine_module)
    created, release = threading.Event(), threading.Event()
    class DelayedLaunch:
        def launch(self, markers):
            child = sandbox.launch(markers); created.set()
            release.wait(timeout=5)
            return child
    engine = engine_module.EngineProcess(sandbox.root, DelayedLaunch())
    marker = str(uuid4()); engine.bind(marker, marker)
    task = asyncio.create_task(engine.command({'op': 'version'}))
    assert await asyncio.to_thread(created.wait, 5), 'Native child did not start'
    task.cancel(); release.set()
    try:
        await task
        raise AssertionError('Cancelled start did not propagate')
    except asyncio.CancelledError:
        pass
    assert engine.process is None
    assert not any(marker in process.cmdline() for process in psutil.process_iter()
        if process.name().lower() == 'python.exe')
    report['cancelled_launch_stops_child'] = True
    result = {'status': 'passed', 'production_modified': False, 'checks': report}
    path = HERE.parents[1] / 'artifacts/duel-sandbox-report.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__': asyncio.run(run())
