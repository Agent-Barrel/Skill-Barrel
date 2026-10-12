"""PTY wrapper: spawn + background reader thread + write helpers.

Backend is pywinpty (ConPTY) on Windows and ptyprocess (POSIX pty) elsewhere;
pywinpty mirrors the ptyprocess API, so both expose the same surface
(``spawn(argv, cwd=, env=, dimensions=(rows, cols))``, ``read``, ``write``,
``sendcontrol``, ``isalive``, ``setwinsize``, ``terminate(force=)``, ``pid``).

The reader thread keeps a raw byte/char log, feeds a callback (the pyte screen),
and tracks ``last_output_ts`` for the runner's adaptive stall detection. When
``mirror`` is True it also echoes PTY output to stdout (used during takeover).
"""
from __future__ import annotations

import codecs
import os
import signal
import subprocess
import sys
import threading
import time

_IS_WINDOWS = sys.platform == "win32"
if _IS_WINDOWS:
    from winpty import PtyProcess as _PtyBackend
else:
    from ptyprocess import PtyProcessUnicode as _PtyBackend

# Cap on ONE generation of the raw PTY log. Past it the log ROTATES
# (pty-<sid>.log -> pty-<sid>.log.1 -> .log.2 …, `log_generations` kept) and
# keeps writing, so the END of a long session -- the part a post-mortem needs
# -- is always present. (It used to stop writing at the cap: the 10-hour
# session in the autonomy record lost exactly its tail.) Bytes are counted as
# UTF-8, not characters.
DEFAULT_MAX_LOG_BYTES = 50 * 1024 * 1024
DEFAULT_LOG_GENERATIONS = 2


class PtySession:
    def __init__(self, argv, cwd, cols, rows, env=None, raw_log_path=None,
                 on_data=None, max_log_bytes=DEFAULT_MAX_LOG_BYTES,
                 log_generations=DEFAULT_LOG_GENERATIONS):
        self.argv = list(argv)
        self.cwd = cwd
        self.cols = cols
        self.rows = rows
        self.env = env
        self.raw_log_path = raw_log_path
        self.on_data = on_data
        self.max_log_bytes = max_log_bytes
        self.log_generations = max(0, int(log_generations))
        # winpty.PtyProcess on Windows, ptyprocess.PtyProcessUnicode on POSIX.
        self.proc = None
        self.child_pid: int | None = None
        self._raw = None
        self._log_bytes = 0
        self._log_generation = 0
        # The reader thread writes and rotates; the owner thread closes. One
        # lock and a closed flag keep a rotation from racing close_log().
        self._log_lock = threading.Lock()
        self._log_closed = False
        self._thread: threading.Thread | None = None
        self.last_output_ts = time.monotonic()
        self.mirror = False
        self.write_errors = 0
        self.last_write_error: str | None = None

    def spawn(self) -> None:
        if self.raw_log_path:
            self._raw = open(
                self.raw_log_path, "w", encoding="utf-8", errors="replace", newline=""
            )
        self.proc = _PtyBackend.spawn(
            self.argv, cwd=self.cwd, env=self.env, dimensions=(self.rows, self.cols)
        )
        if not _IS_WINDOWS:
            # PtyProcessUnicode defaults to a STRICT utf-8 incremental decoder;
            # a single invalid byte would raise in read(), hit _read_loop's bare
            # `except Exception: break`, and silently kill the screen feed.
            # Match pywinpty's lossy behavior instead.
            try:
                self.proc.decoder = codecs.getincrementaldecoder("utf-8")(
                    errors="replace"
                )
            except Exception:
                pass
        # Record the spawned child's PID so teardown can sweep its process tree
        # (MCP servers / node helpers the child launches). This is the spawned
        # session, never the caller's own process.
        self.child_pid = getattr(self.proc, "pid", None)
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while True:
            try:
                data = self.proc.read(4096)
            except EOFError:
                break
            except Exception:
                break
            if not data:
                if not self.proc.isalive():
                    break
                time.sleep(0.02)
                continue
            self.last_output_ts = time.monotonic()
            self._log_write(data)
            if self.mirror:
                try:
                    sys.stdout.write(data)
                    sys.stdout.flush()
                except Exception:
                    pass
            if self.on_data:
                try:
                    self.on_data(data)
                except Exception:
                    pass

    # ------------------------------------------------------------ raw log
    def _log_write(self, data) -> None:
        with self._log_lock:
            if self._raw is None or self._log_closed:
                return
            try:
                n = (len(data.encode("utf-8", "replace"))
                     if isinstance(data, str) else len(data))
                # Rotate BEFORE the write that would cross the cap, so the
                # newest output is always in the live file, never in `.1`.
                if self._log_bytes and self._log_bytes + n > self.max_log_bytes:
                    self._rotate_locked()
                self._raw.write(data)
                self._raw.flush()
                self._log_bytes += n
            except Exception:
                pass

    def _rotate_locked(self) -> None:
        """Close the current generation, shift the kept ones, reopen. Files are
        renamed only after the handle is closed (Windows cannot rename an open
        file). Caller holds _log_lock."""
        base = str(self.raw_log_path)
        self._raw.write("\n[pty log rotated after %d bytes -> %s.1]\n"
                        % (self._log_bytes, base))
        self._raw.flush()
        self._raw.close()
        self._raw = None
        for i in range(self.log_generations, 1, -1):
            src, dst = "%s.%d" % (base, i - 1), "%s.%d" % (base, i)
            if os.path.exists(src):
                os.replace(src, dst)
        if self.log_generations >= 1:
            os.replace(base, base + ".1")
        self._log_generation += 1
        self._log_bytes = 0
        self._raw = open(base, "w", encoding="utf-8", errors="replace", newline="")
        self._raw.write("[pty log generation %d; earlier output in %s.1]\n"
                        % (self._log_generation, base))
        self._raw.flush()

    def log_paths(self) -> list[str]:
        """The current log first, then the kept generations that exist."""
        if not self.raw_log_path:
            return []
        base = str(self.raw_log_path)
        out = [base]
        for i in range(1, self.log_generations + 1):
            p = "%s.%d" % (base, i)
            if os.path.exists(p):
                out.append(p)
        return out

    def write(self, s: str) -> None:
        try:
            self.proc.write(s)
        except Exception as e:
            # Keep swallowing (the runner's stall/EOF path handles a dead pipe),
            # but record it so callers/tests can observe a failed write instead
            # of it being completely silent.
            self.write_errors += 1
            self.last_write_error = repr(e)

    def sendcontrol(self, ch: str) -> None:
        try:
            self.proc.sendcontrol(ch)
        except Exception:
            pass

    def isalive(self) -> bool:
        try:
            return self.proc is not None and self.proc.isalive()
        except Exception:
            return False

    def setwinsize(self, rows: int, cols: int) -> None:
        try:
            self.proc.setwinsize(rows, cols)
        except Exception:
            pass

    def terminate(self) -> None:
        try:
            self.proc.terminate(force=True)
        except Exception:
            pass
        # Belt-and-braces: force-terminating the ConPTY child can orphan
        # grandchildren (MCP servers, node helpers). Sweep the child's whole tree
        # by PID. This targets only the process WE spawned (self.child_pid), never
        # the caller's session.
        self._kill_tree()

    def _kill_tree(self) -> None:
        if not self.child_pid:
            return
        if _IS_WINDOWS:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.child_pid)],
                    capture_output=True,
                )
            except Exception:
                pass
            return
        # ptyprocess spawns via pty.fork(), whose child calls os.setsid(): the
        # child leads its own process group, so pgid == child pid. killpg on
        # that id sweeps the grandchildren (MCP servers, node helpers) too, and
        # keeps working after the leader itself was reaped while orphans
        # survive — which is why we use child_pid directly instead of
        # os.getpgid(child_pid) (getpgid raises once the leader is gone).
        try:
            if self.child_pid != os.getpgrp():
                os.killpg(self.child_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            pass

    def close(self) -> None:
        """Join the reader thread (best-effort) and close the log."""
        if self._thread is not None:
            try:
                self._thread.join(timeout=2.0)
            except Exception:
                pass
        self.close_log()

    def close_log(self) -> None:
        with self._log_lock:
            self._log_closed = True
            if self._raw:
                try:
                    self._raw.close()
                except Exception:
                    pass
                self._raw = None
