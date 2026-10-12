"""Private bounded JSON-lines transport to one disposable native core process."""
import asyncio
import json
from pathlib import Path
import subprocess
import importlib.util

HERE = Path(__file__).resolve().parent


class EngineProcess:
    def __init__(self, root, sandbox=None):
        self.root, self.process = Path(root), None
        self.markers = []
        self.job = None
        self.sandbox = sandbox

    def bind(self, run_id, instance):
        if self.process is not None: raise ValueError('Worker already spawned')
        self.markers = ['--hub-run', run_id, '--hub-instance', instance]

    async def command(self, command):
        try:
            if not self.process:
                if self.sandbox is not None:
                    spawn = asyncio.create_task(asyncio.to_thread(self.sandbox.launch, self.markers))
                else:
                    spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                        str((self.root / 'python32/python.exe').resolve()), str((HERE / 'core_worker.py').resolve()), str(self.root.resolve()), *self.markers,
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL, limit=8 * 1024 * 1024,
                        # Limits apply before the interpreter/library can execute.
                        creationflags=(subprocess.CREATE_NO_WINDOW | 0x4) if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0))
                try: self.process = await asyncio.shield(spawn)
                except asyncio.CancelledError:
                    # A cancelled subprocess creation may still produce a child.
                    # Acquire its handle before the outer cleanup can release stock.
                    self.process = await spawn
                    raise
                if self.sandbox is None:
                    spec = importlib.util.spec_from_file_location('sdoycc_windows_job', HERE / 'windows_job.py')
                    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                    self.job = module.Job(self.process.pid)
                    self.job.resume(self.process.pid)
            async def exchange():
                data = (json.dumps(command) + '\n').encode()
                if len(data) > 65536: raise ValueError('IPC command limit')
                self.process.stdin.write(data)
                await self.process.stdin.drain()
                result = json.loads(await self.process.stdout.readline())
                if not isinstance(result, dict) or 'error' in result: raise RuntimeError('Worker rejected command')
                return result
            return await asyncio.wait_for(exchange(), timeout=5)
        except BaseException as error:
            if self.process is None and getattr(error, 'owned_process', None) is not None:
                self.process = error.owned_process
            await asyncio.shield(self.close())
            raise

    async def close(self):
        if self.process:
            if self.process.returncode is None: self.process.kill()
            await asyncio.wait_for(self.process.wait(), timeout=5)
            self.process = None
        if self.job:
            self.job.close(); self.job = None
