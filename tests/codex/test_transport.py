import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from step2step.codex.transport import Transport, RpcError, ProtocolError, child_env
from step2step.contracts import ControlError


SERVER = r'''
import json, sys, time, os
for line in sys.stdin.buffer:
    msg = json.loads(line)
    method = msg.get('method')
    if method == 'exit': sys.exit(0)
    if method == 'hang': time.sleep(60)
    if method == 'malformed':
        print('not-json', flush=True)
        continue
    if method == 'error':
        print(json.dumps({'id':msg['id'],'error':{'code':-32601,'message':'unknown method'}}),flush=True)
        continue
    if method == 'unicode':
        wire=(json.dumps({'id':msg['id'],'result':{'text':'한글✓'}},ensure_ascii=False)+'\n').encode()
        for b in wire:
            os.write(1,bytes([b]))
        continue
    if method == 'event-first':
        print(json.dumps({'method':'event','params':{'threadId':'x'}}),flush=True)
    if 'id' in msg:
        print(json.dumps({'id':msg['id'],'result':msg.get('params',{})}),flush=True)
'''


@pytest.fixture
def transport(monkeypatch, tmp_path):
    import step2step.codex.transport as mod
    popen = subprocess.Popen
    def spawn(argv, **kwargs):
        return popen([sys.executable, '-u', '-c', SERVER] if argv[0] == 'fake-codex' else argv, **kwargs)
    monkeypatch.setattr(mod.subprocess, 'Popen', spawn)
    t = Transport(executable='fake-codex', cwd=str(tmp_path), timeout=0.15)
    yield t
    t.close(force=True)
    assert t.proc.poll() is not None


def test_partial_utf8_and_event_before_response(transport):
    assert transport.request('unicode') == {'text':'한글✓'}
    assert transport.request('event-first', {'x':1}) == {'x':1}
    assert transport.events.get(timeout=1)['method'] == 'event'


def test_concurrent_rpc_ids_route_to_their_waiter(transport):
    answers = []
    threads = [threading.Thread(target=lambda i=i: answers.append(transport.request('echo',{'i':i}))) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sorted(r['i'] for r in answers) == list(range(10))


def test_server_errors_leave_connection_usable(transport):
    with pytest.raises(RpcError) as err: transport.request('error')
    assert err.value.error['code'] == -32601
    assert transport.request('echo', {'ok':True}) == {'ok':True}


@pytest.mark.parametrize('method', ['exit','hang','malformed'])
def test_disconnect_timeout_and_malformed_are_terminal(transport, method):
    with pytest.raises(ControlError): transport.request(method)
    assert not transport.is_alive()
    with pytest.raises(ControlError): transport.request('echo')


def test_no_api_key_or_parent_identity_in_child_env(monkeypatch):
    for key in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'ANTHROPIC_API_KEY', 'CLAUDECODE', 'CODEX_THREAD_ID'):
        monkeypatch.setenv(key, 'do-not-inherit')
    monkeypatch.setenv('CODEX_HOME', '/custom/subscription-home')
    env = child_env()
    assert env['CODEX_HOME'] == '/custom/subscription-home'
    assert 'do-not-inherit' not in env.values()


def test_codex_import_does_not_load_claude_stack():
    result = subprocess.run([sys.executable, '-c',
        'import sys; import step2step.codex; '
        'assert not any(n.startswith("step2step.claude") for n in sys.modules); '
        'assert "pyte" not in sys.modules'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name == 'nt', reason='POSIX detached process cleanup')
def test_detached_descendant_cleanup_does_not_kill_unrelated_process(tmp_path):
    import signal
    import time
    from step2step.codex.processes import descendants, signal_owned
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    parent = subprocess.Popen([sys.executable, '-u', '-c',
        'import subprocess,sys,time; '
        'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],start_new_session=True); '
        'print(p.pid,flush=True);time.sleep(60)'], stdout=subprocess.PIPE, text=True, start_new_session=True)
    child_pid = int(parent.stdout.readline())
    try:
        owned = descendants(parent.pid)
        assert child_pid in owned and unrelated.pid not in owned
        signal_owned(owned, signal.SIGKILL)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = subprocess.run(['ps','-p',str(child_pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
            if not state or state.startswith('Z'): break
            time.sleep(0.02)
        else: pytest.fail('Detached owned process survived cleanup')
        assert unrelated.poll() is None
    finally:
        for proc in (parent, unrelated):
            proc.kill();proc.wait()
        parent.stdout.close()


def test_blocked_stdin_write_has_a_deadline_and_can_be_torn_down(transport):
    import time
    transport.notify('hang')
    started = time.monotonic()
    with pytest.raises(ControlError, match='timed out'):
        transport.request('echo', {'payload':'x'*1_000_000})
    assert time.monotonic() - started < 1
    transport.close(force=True)
    assert transport.proc.poll() is not None
    assert not transport._writer.is_alive()


def test_failed_process_inventory_still_stops_owned_server(transport, monkeypatch):
    import step2step.codex.transport as mod
    def unavailable(*args): raise OSError('ps unavailable')
    monkeypatch.setattr(mod, 'descendants', unavailable)
    transport.close(force=True)
    assert transport.proc.poll() is not None
