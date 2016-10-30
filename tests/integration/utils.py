import contextlib
import socket

import requests
import websocket


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


@contextlib.contextmanager
def devtools_proxy_ws(port, timeout=2):
    tabs = requests.get('http://localhost:{}/json/list'.format(port)).json()
    tab = next(tab for tab in tabs if tab.get('type') == 'page')
    devtools_url = tab['webSocketDebuggerUrl']

    ws = websocket.create_connection(devtools_url)
    ws.timeout = timeout
    yield ws
    ws.close()
