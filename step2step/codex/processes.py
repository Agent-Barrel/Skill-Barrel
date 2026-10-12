"""Track owned POSIX descendants, including commands that call setsid()."""
import os
import subprocess


def _table():
    output = subprocess.check_output(["ps", "-axo", "pid=,ppid=,lstart="], text=True, timeout=3)
    result = {}
    for line in output.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3:
            result[int(fields[0])] = (int(fields[1]), fields[2])
    return result


def descendants(root_pid):
    """Record birth times so cleanup cannot signal a recycled, unrelated PID."""
    if os.name == "nt":
        return {}
    table = _table()
    owned = {root_pid}
    while True:
        found = {pid for pid, (parent, _) in table.items() if parent in owned}
        if found <= owned:
            break
        owned.update(found)
    return {pid: table[pid][1] for pid in owned if pid != root_pid and pid in table}


def signal_owned(owned, sig):
    if not owned:
        return
    current = _table()
    for pid, birth in owned.items():
        if current.get(pid, (None, None))[1] == birth:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
