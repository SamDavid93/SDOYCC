"""Windows AppContainer launcher; no network capabilities or inherited environment.

Reference: https://learn.microsoft.com/windows/win32/secauthz/implementing-an-appcontainer
Only the verified engine package and a staged worker receive read/execute ACLs.
The profile is installation-specific and reused across concurrent workers.
"""
import asyncio
import ctypes as C
from ctypes import wintypes as W
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import msvcrt
import json


class SecurityAttributes(C.Structure):
    _fields_ = [('size', W.DWORD), ('descriptor', C.c_void_p), ('inherit', W.BOOL)]


class StartupInfo(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR),
        ('title', W.LPWSTR), ('x', W.DWORD), ('y', W.DWORD), ('cx', W.DWORD),
        ('cy', W.DWORD), ('chars_x', W.DWORD), ('chars_y', W.DWORD),
        ('fill', W.DWORD), ('flags', W.DWORD), ('show', W.WORD),
        ('reserved_size', W.WORD), ('reserved_pointer', C.c_void_p),
        ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]


class StartupInfoEx(C.Structure):
    _fields_ = [('info', StartupInfo), ('attributes', C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


class Capabilities(C.Structure):
    _fields_ = [('sid', C.c_void_p), ('capabilities', C.c_void_p),
        ('count', W.DWORD), ('reserved', W.DWORD)]


def api(library, name, args, result):
    fn = getattr(library, name); fn.argtypes = args; fn.restype = result
    return fn


class LaunchCleanupError(RuntimeError):
    def __init__(self, process):
        super().__init__('Sandbox launch failed; child termination remains unconfirmed')
        self.owned_process = process


class Sandbox:
    def __init__(self, root, script):
        source_root = Path(root).resolve()
        key = hashlib.sha256(str(source_root).encode()).hexdigest()[:20]
        # The mounted workspace drive need not allow AppContainer traversal.
        # Use an isolated copy on the user's Windows system volume instead.
        self.root = Path(os.environ['LOCALAPPDATA']) / 'SDOYCC-Duel-Runtime' / key
        self.root.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((source_root / 'verified-files.json').read_text(encoding='utf8'))
        expected_scripts = set()
        checked_directories = set()
        for name, digest in manifest.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts: raise ValueError('Unsafe sandbox package path')
            if relative.parts[0] not in ('python32', 'cards', 'scripts') and name != 'ocgcore.dll': continue
            source, target = source_root / relative, self.root / relative
            for directory, boundary in ((source.parent, source_root), (target.parent, self.root)):
                if directory not in checked_directories:
                    if not directory.resolve().is_relative_to(boundary): raise ValueError('Unsafe sandbox package directory')
                    checked_directories.add(directory)
            if source.is_symlink() or target.is_symlink(): raise ValueError('Sandbox package symlink rejected')
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Unverified sandbox source: ' + name)
            if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
            if relative.parts[0] == 'scripts': expected_scripts.add(target)
        if any(path not in expected_scripts for path in (self.root / 'scripts').rglob('*.lua')):
            raise ValueError('Unverified extra script in sandbox runtime')
        self.script = self.root / 'worker/core_worker.py'
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.userenv = C.WinDLL('userenv', use_last_error=True)
        self.advapi = C.WinDLL('advapi32', use_last_error=True)
        spec = importlib.util.spec_from_file_location('sdoycc_sandbox_job', Path(__file__).with_name('windows_job.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.job_type = module.Job
        self.name = 'SDOYCC.Duel.' + hashlib.sha256(str(self.root).encode()).hexdigest()[:20]
        self.sid = C.c_void_p()
        create = api(self.userenv, 'CreateAppContainerProfile',
            [W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, C.c_void_p, W.DWORD, C.POINTER(C.c_void_p)], C.c_long)
        result = create(self.name, self.name, 'Isolated native duel worker', None, 0, C.byref(self.sid))
        if result == -2147024713:  # HRESULT_FROM_WIN32(ERROR_ALREADY_EXISTS)
            derive = api(self.userenv, 'DeriveAppContainerSidFromAppContainerName',
                [W.LPCWSTR, C.POINTER(C.c_void_p)], C.c_long)
            result = derive(self.name, C.byref(self.sid))
        if result < 0: raise OSError('AppContainer profile failed: ' + hex(result & 0xffffffff))
        convert = api(self.advapi, 'ConvertSidToStringSidW', [C.c_void_p, C.POINTER(W.LPWSTR)], W.BOOL)
        value = W.LPWSTR()
        if not convert(self.sid, C.byref(value)): raise C.WinError(C.get_last_error())
        self.sid_text = value.value
        api(self.kernel, 'LocalFree', [C.c_void_p], C.c_void_p)(C.cast(value, C.c_void_p))
        self.script.parent.mkdir(exist_ok=True)
        content = Path(script).read_bytes()
        if not self.script.exists() or self.script.read_bytes() != content:
            self.script.write_bytes(content)
        # No inherited grant on root: auxiliary snapshots/configuration are excluded.
        self.grant(self.root, '(RX)')
        self.grant(self.root / 'ocgcore.dll', '(RX)')
        for name in ('python32', 'cards', 'scripts', 'worker'):
            self.grant(self.root / name, '(OI)(CI)(RX)', recursive=True)

    def grant(self, path, rights, recursive=False):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Sandbox ACL outside runtime')
        command = ['icacls', str(path), '/grant:r', '*' + self.sid_text + ':' + rights, '/Q']
        if recursive: command.append('/T')
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)

    def launch(self, markers, script=None):
        script = Path(script) if script is not None else self.script
        if not script.resolve().is_relative_to(self.script.parent.resolve()):
            raise ValueError('Sandbox script outside staged worker directory')
        kernel = self.kernel
        close = api(kernel, 'CloseHandle', [W.HANDLE], W.BOOL)
        pipe = api(kernel, 'CreatePipe', [C.POINTER(W.HANDLE), C.POINTER(W.HANDLE), C.POINTER(SecurityAttributes), W.DWORD], W.BOOL)
        inherit = api(kernel, 'SetHandleInformation', [W.HANDLE, W.DWORD, W.DWORD], W.BOOL)
        init = api(kernel, 'InitializeProcThreadAttributeList', [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL)
        update = api(kernel, 'UpdateProcThreadAttribute', [C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL)
        delete = api(kernel, 'DeleteProcThreadAttributeList', [C.c_void_p], None)
        create = api(kernel, 'CreateProcessW', [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p,
            W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.c_void_p, C.POINTER(ProcessInfo)], W.BOOL)
        stdin_read, stdin_write, stdout_read, stdout_write, stderr = (W.HANDLE() for _ in range(5))
        handles = [stdin_read, stdin_write, stdout_read, stdout_write, stderr]
        attr = None; initialized = False; info = ProcessInfo(); job = None
        try:
            sa = SecurityAttributes(C.sizeof(SecurityAttributes), None, True)
            if not pipe(C.byref(stdin_read), C.byref(stdin_write), C.byref(sa), 1 << 20): raise C.WinError(C.get_last_error())
            if not pipe(C.byref(stdout_read), C.byref(stdout_write), C.byref(sa), 1 << 20): raise C.WinError(C.get_last_error())
            stderr.value = api(kernel, 'CreateFileW', [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p,
                W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)('NUL', 0x40000000, 3, C.byref(sa), 3, 0, None)
            if stderr.value == C.c_void_p(-1).value:
                stderr.value = None; raise C.WinError(C.get_last_error())
            for handle in (stdin_write, stdout_read):
                if not inherit(handle, 1, 0): raise C.WinError(C.get_last_error())
            size = C.c_size_t()
            init(None, 2, 0, C.byref(size))
            attr = C.create_string_buffer(size.value)
            if not init(attr, 2, 0, C.byref(size)): raise C.WinError(C.get_last_error())
            initialized = True
            caps = Capabilities(self.sid, None, 0, 0)
            inherited = (W.HANDLE * 3)(stdin_read.value, stdout_write.value, stderr.value)
            for attribute, value in ((0x20009, caps), (0x20002, inherited)):
                if not update(attr, 0, attribute, C.byref(value), C.sizeof(value), None, None): raise C.WinError(C.get_last_error())
            startup = StartupInfoEx(); startup.info.cb = C.sizeof(startup)
            startup.info.flags = 0x100; startup.info.stdin = stdin_read.value
            startup.info.stdout = stdout_write.value; startup.info.stderr = stderr.value
            startup.attributes = C.cast(attr, C.c_void_p)
            executable = str(self.root / 'python32/python.exe')
            command = C.create_unicode_buffer(subprocess.list2cmdline([executable, str(script), str(self.root), *markers]))
            # Never propagate server tokens, connection strings or Python paths.
            values = {key: os.environ[key] for key in ('SystemRoot', 'SystemDrive', 'WINDIR',
                'USERPROFILE', 'LOCALAPPDATA', 'APPDATA') if key in os.environ}
            values['PYTHONDONTWRITEBYTECODE'] = '1'
            environment = C.create_unicode_buffer('\0'.join(key + '=' + value
                for key, value in sorted(values.items(), key=lambda item: item[0].upper())) + '\0\0')
            if not create(executable, command, None, None, True, 0x80000 | 0x400 | 0x4 | 0x8000000,
                    environment, str(self.root), C.byref(startup), C.byref(info)):
                raise C.WinError(C.get_last_error())
            job = self.job_type(info.pid)
            job.resume(info.pid)
            result = Process(kernel, info.process, info.pid, stdin_write.value, stdout_read.value, job)
            info.process = None; stdin_write.value = stdout_read.value = None; job = None
            return result
        finally:
            cleanup_error = None
            if info.process:
                api(kernel, 'TerminateProcess', [W.HANDLE, W.UINT], W.BOOL)(info.process, 1)
                result = api(kernel, 'WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD)(info.process, 5000)
                if result != 0:
                    # Keep ownership in the caller instead of reporting a clean
                    # failed spawn while a potentially live child is untracked.
                    owned = Process(kernel, info.process, info.pid, stdin_write.value, stdout_read.value, job)
                    info.process = None; stdin_write.value = stdout_read.value = None; job = None
                    cleanup_error = LaunchCleanupError(owned)
                else:
                    close(info.process)
            if job: job.close()
            if info.thread: close(info.thread)
            for handle in handles:
                if handle.value: close(handle)
            if initialized: delete(attr)
            if cleanup_error: raise cleanup_error


class Input:
    def __init__(self, stream): self.stream, self.pending = stream, b''
    def write(self, data): self.pending = data
    async def drain(self):
        data, self.pending = self.pending, b''
        await asyncio.to_thread(self.stream.write, data)


class Output:
    def __init__(self, stream): self.stream = stream
    async def readline(self):
        data = await asyncio.to_thread(self.stream.readline, 8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024: raise ValueError('IPC response limit')
        return data


class Process:
    def __init__(self, kernel, handle, pid, stdin, stdout, job):
        self.kernel, self.handle, self.pid, self.job = kernel, handle, pid, job
        self.stdin = Input(os.fdopen(msvcrt.open_osfhandle(stdin, os.O_WRONLY | os.O_BINARY), 'wb', buffering=0))
        self.stdout = Output(os.fdopen(msvcrt.open_osfhandle(stdout, os.O_RDONLY | os.O_BINARY), 'rb'))
        self.code = None

    @property
    def returncode(self):
        if self.handle:
            code = W.DWORD()
            if not api(self.kernel, 'GetExitCodeProcess', [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL)(self.handle, C.byref(code)):
                raise C.WinError(C.get_last_error())
            if code.value != 259: self.code = code.value
        return self.code

    def kill(self):
        if not api(self.kernel, 'TerminateProcess', [W.HANDLE, W.UINT], W.BOOL)(self.handle, 1):
            if self.returncode is None: raise C.WinError(C.get_last_error())

    async def wait(self):
        wait = api(self.kernel, 'WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD)
        result = await asyncio.to_thread(wait, self.handle, 5000)
        if result != 0: raise RuntimeError('Sandbox worker termination unconfirmed')
        code = self.returncode
        self.stdin.stream.close(); self.stdout.stream.close()
        api(self.kernel, 'CloseHandle', [W.HANDLE], W.BOOL)(self.handle); self.handle = None
        if self.job: self.job.close(); self.job = None
        return code
