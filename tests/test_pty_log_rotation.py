"""PtySession raw log: rotates at the cap instead of stopping, keeps N
generations, counts UTF-8 bytes, and never races close_log()."""
import threading

from step2step.terminal.pty_session import PtySession


def _session(tmp_path, cap=40, generations=2):
    p = PtySession([], cwd=str(tmp_path), cols=80, rows=24,
                   raw_log_path=str(tmp_path / "pty-x.log"),
                   max_log_bytes=cap, log_generations=generations)
    p._raw = open(p.raw_log_path, "w", encoding="utf-8", errors="replace", newline="")
    return p


def test_rotates_and_keeps_the_tail(tmp_path):
    p = _session(tmp_path)
    for i in range(6):
        p._log_write("chunk-%d-" % i + "x" * 30)
    p.close_log()
    base = tmp_path / "pty-x.log"
    assert base.exists() and (tmp_path / "pty-x.log.1").exists()
    assert (tmp_path / "pty-x.log.2").exists()
    assert not (tmp_path / "pty-x.log.3").exists()      # only 2 generations
    current = base.read_text(encoding="utf-8")
    assert "chunk-5-" in current                         # the END is in the live file
    assert "[pty log generation" in current
    older = (tmp_path / "pty-x.log.1").read_text(encoding="utf-8")
    assert "[pty log rotated after" in older
    assert p.log_paths() == [str(base), str(base) + ".1", str(base) + ".2"]


def test_counts_utf8_bytes_not_characters(tmp_path):
    p = _session(tmp_path, cap=30, generations=1)
    p._log_write("한" * 10)          # 30 bytes (10 characters): fills the cap
    p._log_write("한" * 10)          # would cross it -> rotates first
    p.close_log()
    assert (tmp_path / "pty-x.log.1").exists()
    assert (tmp_path / "pty-x.log").read_text(encoding="utf-8").endswith("한" * 10)


def test_writes_after_close_are_dropped(tmp_path):
    p = _session(tmp_path, cap=10_000)
    p._log_write("before")
    p.close_log()
    p._log_write("after")
    assert (tmp_path / "pty-x.log").read_text(encoding="utf-8") == "before"
    assert p.log_paths() == [str(tmp_path / "pty-x.log")]


def test_concurrent_writes_and_close_do_not_raise(tmp_path):
    p = _session(tmp_path, cap=64, generations=2)
    stop = threading.Event()

    def writer():
        while not stop.is_set():
            p._log_write("y" * 20)

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    for _ in range(50):
        p._log_write("z" * 20)
    p.close_log()
    stop.set()
    t.join(timeout=2.0)
    assert p._raw is None


def test_zero_generations_truncates_in_place(tmp_path):
    p = _session(tmp_path, cap=20, generations=0)
    p._log_write("a" * 25)
    p._log_write("tail")
    p.close_log()
    assert "tail" in (tmp_path / "pty-x.log").read_text(encoding="utf-8")
    assert not (tmp_path / "pty-x.log.1").exists()
