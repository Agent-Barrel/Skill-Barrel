"""Owned, stdio-only Codex app-server connection. No global daemon attachment."""
from __future__ import annotations

import json
import atexit
import os
import pathlib
import queue
import shutil
import signal
import subprocess
import threading
import time

from ..contracts import ControlError
from .processes import descendants, signal_owned


_OWNED = set()
_OWNED_LOCK = threading.Lock()


@atexit.register
def _close_owned():
    with _OWNED_LOCK:
        owned = list(_OWNED)
    for transport in owned:
        try:
            transport.close(force=True)
        except Exception:
            pass


class ProtocolError(ControlError):
    pass


class RpcError(ControlError):
    def __init__(self, method: str, error: dict):
        super().__init__(f"{method}: {error.get('message', error)}")
        self.method, self.error = method, error


def resolve_codex(explicit=None) -> str:
    if explicit:
        return str(explicit)
    found = shutil.which("codex")
    if found:
        return found
    path = pathlib.Path.home() / ".local/bin" / ("codex.exe" if os.name == "nt" else "codex")
    if path.is_file():
        return str(path)
    raise FileNotFoundError("codex executable not found on PATH or ~/.local/bin")


def child_env() -> dict[str, str]:
    """Keep the CLI's own login; don't inherit API billing or parent identity."""
    excluded = {"OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID",
                "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CODEX_THREAD_ID",
                "CODEX_TURN_ID", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"}
    return {k: v for k, v in os.environ.items()
            if k.upper() not in excluded and not k.upper().startswith("CLAUDE")}


class Transport:
    def __init__(self, *, executable=None, cwd=None, timeout=30.0, stderr_path=None):
        self.timeout = timeout
        self.events: queue.Queue[dict] = queue.Queue()
        self._pending: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self._writes = queue.Queue()
        self._counter = 0
        self._closed = False
        self._error = None
        argv = [resolve_codex(executable), "app-server", "--listen", "stdio://",
                "-c", 'forced_login_method="chatgpt"',
                "-c", 'model_provider="openai"']
        if cwd:
            # Load authorized project config using invocation-only trust.
            # SessionHandle also boots read-only to prevent native auto-trust writes.
            root = json.dumps(str(pathlib.Path(cwd).resolve()))
            argv += ["-c", f'projects.{root}.trust_level="trusted"']
        self._stderr = open(stderr_path, "ab") if stderr_path else subprocess.DEVNULL
        try:
            self.proc = subprocess.Popen(
                argv, cwd=cwd, env=child_env(), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self._stderr,
                start_new_session=os.name != "nt",
            )
        except BaseException:
            if hasattr(self._stderr, "close"):
                self._stderr.close()
            raise
        self._reader = threading.Thread(target=self._read, daemon=True,
                                        name=f"codex-rpc-{self.proc.pid}")
        self._writer = threading.Thread(target=self._write, daemon=True,
                                        name=f"codex-write-{self.proc.pid}")
        self._reader.start()
        self._writer.start()
        with _OWNED_LOCK:
            _OWNED.add(self)

    def _fail(self, exc):
        with self._lock:
            self._error = self._error or exc
            for pending in self._pending.values():
                pending.put(exc)
        self.events.put({"method": "transport/closed", "params": {"message": str(exc)}})

    def _read(self):
        try:
            for line in self.proc.stdout:
                msg = json.loads(line)
                if not isinstance(msg, dict):
                    raise ProtocolError("app-server sent a non-object message")
                if "method" in msg:
                    self.events.put(msg)
                elif "id" in msg:
                    with self._lock:
                        pending = self._pending.get(msg["id"])
                    if pending is not None:
                        pending.put(msg)
                else:
                    raise ProtocolError("app-server message has neither method nor id")
        except (ValueError, OSError, TypeError) as exc:
            self._fail(ProtocolError(f"Invalid app-server stream: {exc}"))
        except ProtocolError as exc:
            self._fail(exc)
        finally:
            if not self._closed and not self._error:
                self._fail(ControlError("app-server disconnected"))

    def _write(self):
        while True:
            task = self._writes.get()
            if task is None:
                return
            msg, finished = task
            if self._closed or self._error:
                finished.put(ControlError(f"app-server unavailable: {self._error or 'closed'}"))
                continue
            try:
                self.proc.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode())
                self.proc.stdin.flush()
            except (OSError, ValueError) as exc:
                self._fail(ControlError(f"app-server write failed: {exc}"))
                finished.put(self._error)
            except (TypeError, UnicodeError) as exc:
                finished.put(ControlError(f"Invalid outbound message: {exc}"))
            else:
                finished.put(None)

    def _send(self, msg, *, timeout=None):
        if self._closed or self._error:
            raise ControlError(f"app-server unavailable: {self._error or 'closed'}")
        finished = queue.Queue()
        self._writes.put((msg, finished))
        try:
            failure = finished.get(timeout=self.timeout if timeout is None else timeout)
        except queue.Empty as exc:
            failure = ControlError("app-server write timed out; delivery is uncertain; resume explicitly")
            self._fail(failure)
            raise failure from exc
        if failure:
            raise failure

    def request(self, method, params=None, *, timeout=None):
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        with self._lock:
            self._counter += 1
            request_id = self._counter
            pending = self._pending[request_id] = queue.Queue()
        try:
            self._send({"id": request_id, "method": method, "params": params or {}},
                       timeout=max(0.0, deadline-time.monotonic()))
            try:
                msg = pending.get(timeout=max(0.0, deadline-time.monotonic()))
            except queue.Empty as exc:
                # The server may have accepted a mutation. Never replay it.
                failure = ControlError(f"{method} timed out; delivery is uncertain; resume explicitly")
                self._fail(failure)
                raise failure from exc
            if isinstance(msg, Exception):
                raise msg
            if "error" in msg:
                raise RpcError(method, msg["error"])
            if "result" not in msg:
                raise ProtocolError(f"{method}: response has no result")
            return msg["result"]
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def notify(self, method, params=None):
        self._send({"method": method, "params": params or {}})

    def respond(self, request_id, result=None, *, error=None):
        self._send({"id": request_id, **({"error": error} if error is not None
                                         else {"result": result or {}})})

    def is_alive(self):
        return not self._closed and self._error is None and self.proc.poll() is None

    def close(self, *, force=False):
        if self._closed:
            return
        force = force or self._error is not None
        self._closed = True
        self._fail(ControlError("app-server closed"))
        self._writes.put(None)
        try:
            owned = descendants(self.proc.pid) if self.proc.poll() is None else {}
        except (OSError, subprocess.SubprocessError):
            owned = {}  # Process-group cleanup still works when ps is unavailable.
        try:
            if not force:
                self._writer.join(timeout=1)
                if not self._writer.is_alive():
                    try:
                        self.proc.stdin.close()
                    except OSError:
                        pass
                    try:
                        self.proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
            if os.name != "nt":
                self._signal_descendants(owned, signal.SIGTERM)
                # A dedicated process group contains only this owned server's children.
                try:
                    os.killpg(self.proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    if self.proc.poll() is None:
                        raise
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    if self.proc.poll() is None:
                        raise
                self._signal_descendants(owned, signal.SIGKILL)
            elif self.proc.poll() is None:
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            self.proc.wait(timeout=5)
        finally:
            self._writer.join(timeout=2)
            self._reader.join(timeout=2)
            # Never block close on a buffered pipe lock held by a stuck I/O thread.
            if not self._writer.is_alive():
                try:
                    self.proc.stdin.close()
                except OSError:
                    pass
            if not self._reader.is_alive():
                self.proc.stdout.close()
            if hasattr(self._stderr, "close"):
                self._stderr.close()
            with _OWNED_LOCK:
                _OWNED.discard(self)

    @staticmethod
    def _signal_descendants(owned, sig):
        try:
            signal_owned(owned, sig)
        except (OSError, subprocess.SubprocessError):
            pass  # Always continue with the owned process-group teardown.
