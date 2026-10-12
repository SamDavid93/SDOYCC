"""Windows kernel lifetime/resource limits, not a filesystem/network sandbox.

ABI: Microsoft JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JobObject class 9.
The non-inherited job handle stays in the supervisor; its loss kills the core.
"""
import ctypes as C
from ctypes import wintypes as W
import os
import psutil


class BasicLimits(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64), ('flags', W.DWORD),
        ('min_working_set', C.c_size_t), ('max_working_set', C.c_size_t), ('active_processes', W.DWORD),
        ('affinity', C.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]


class IoCounters(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in ('reads', 'writes', 'other', 'read_bytes', 'write_bytes', 'other_bytes')]


class ExtendedLimits(C.Structure):
    _fields_ = [('basic', BasicLimits), ('io', IoCounters), ('process_memory', C.c_size_t),
        ('job_memory', C.c_size_t), ('peak_process_memory', C.c_size_t), ('peak_job_memory', C.c_size_t)]


class Job:
    def __init__(self, pid):
        if os.name != 'nt': raise RuntimeError('This pinned worker requires Windows job isolation')
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('CreateJobObjectW', [C.c_void_p, W.LPCWSTR], W.HANDLE),
            ('SetInformationJobObject', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            ('OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            ('AssignProcessToJobObject', [W.HANDLE, W.HANDLE], W.BOOL),
            ('OpenThread', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            ('ResumeThread', [W.HANDLE], W.DWORD),
            ('CloseHandle', [W.HANDLE], W.BOOL)):
            fn = getattr(self.kernel, name); fn.argtypes = args; fn.restype = result
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle: raise C.WinError(C.get_last_error())
        process = None
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000 | 0x100 | 0x8 | 0x2 | 0x400
            limits.basic.active_processes = 1
            limits.basic.process_time = 120 * 10_000_000
            limits.process_memory = 512 * 1024 * 1024
            if not self.kernel.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
            process = self.kernel.OpenProcess(0x100 | 0x1, False, pid)  # SET_QUOTA | TERMINATE
            if not process or not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise C.WinError(C.get_last_error())
        except BaseException:
            self.close(); raise
        finally:
            if process: self.kernel.CloseHandle(process)

    def resume(self, pid):
        """Release only the initial thread after successful job assignment."""
        threads = psutil.Process(pid).threads()
        if len(threads) != 1:
            raise RuntimeError('Suspended worker must have exactly one initial thread')
        thread = self.kernel.OpenThread(0x2, False, threads[0].id)
        if not thread:
            raise C.WinError(C.get_last_error())
        try:
            previous = self.kernel.ResumeThread(thread)
            if previous == 0xffffffff:
                raise C.WinError(C.get_last_error())
            if previous != 1:
                raise RuntimeError('Unexpected worker suspend count')
        finally:
            self.kernel.CloseHandle(thread)

    def close(self):
        if self.handle:
            if not self.kernel.CloseHandle(self.handle): raise C.WinError(C.get_last_error())
            self.handle = None
