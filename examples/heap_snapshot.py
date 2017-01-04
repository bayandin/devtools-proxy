#!/usr/bin/env python3

# https://chromedevtools.github.io/debugger-protocol-viewer/tot/HeapProfiler/

import json

import requests
import selenium
import websocket
from devtools.proxy import CHROME_WRAPPER_PATH
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

if __name__ == '__main__':
    devtools_proxy_port = 9222

    desired_capabilities = DesiredCapabilities.CHROME.copy()
    desired_capabilities['chromeOptions'] = {
        'binary': CHROME_WRAPPER_PATH,
        'args': [
            '--devtools-proxy-binary=devtools-proxy',
            '--devtools-proxy-args=--port {}'.format(devtools_proxy_port),
        ]
    }

    driver = selenium.webdriver.Chrome(desired_capabilities=desired_capabilities)
    try:
        tabs = requests.get('http://localhost:{}/json/list'.format(devtools_proxy_port)).json()
        tab = next(tab for tab in tabs if tab.get('type') == 'page')
        devtools_url = tab['webSocketDebuggerUrl']
        driver.get('https://google.co.uk')

        ws = websocket.create_connection(devtools_url)
        data = {
            "method": "HeapProfiler.enable",
            "params": {},
            "id": 0,
        }
        ws.send(json.dumps(data))
        ws.recv()

        data = {
            "method": "HeapProfiler.takeHeapSnapshot",
            "params": {},
            "id": 0,
        }
        ws.send(json.dumps(data))

        heap_data = ''
        while True:
            raw_data = ws.recv()
            result = json.loads(raw_data)
            if result.get('id') == 0:
                break
            if result.get('method') == 'HeapProfiler.addHeapSnapshotChunk':
                heap_data += result['params']['chunk']

        ws.close()

        with open('example.heapsnapshot', 'w') as f:
            f.write(heap_data)
    finally:
        driver.quit()
