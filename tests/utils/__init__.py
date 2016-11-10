import contextlib
import signal
import socket
import subprocess
import time
from pathlib import Path

import requests
import websocket

PROJECT_DIR = Path(__file__, '../../../').resolve()


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


@contextlib.contextmanager
def devtools_proxy_ws(port, timeout=2):
    tabs = requests.get('http://127.0.0.1:{}/json/list'.format(port)).json()
    tab = next(tab for tab in tabs if tab.get('type') == 'page')
    devtools_url = tab['webSocketDebuggerUrl']

    ws = websocket.create_connection(devtools_url)
    ws.timeout = timeout
    yield ws
    ws.close()


@contextlib.contextmanager
def devtools_proxy(args, env=None):
    _args = ['{}/devtools-proxy.py'.format(PROJECT_DIR)] + [str(arg) for arg in args]
    p = subprocess.Popen(args=_args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    time.sleep(1)  # TODO: find a better way

    yield p
    p.send_signal(signal.SIGINT)
    p.wait(timeout=5)
