#!/usr/bin/env python3

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
            f'--devtools-proxy-args=--port {devtools_proxy_port}',
        ]
    }

    driver = selenium.webdriver.Chrome(desired_capabilities=desired_capabilities)
    try:
        tabs = requests.get(f'http://localhost:{devtools_proxy_port}/json/list').json()
        tab = next(tab for tab in tabs if tab.get('type') == 'page')
        devtools_url = tab['webSocketDebuggerUrl']
        driver.get('https://codepen.io/bayandin/full/xRpROy/')

        ws = websocket.create_connection(devtools_url)
        data = {
            "method": "Emulation.setCPUThrottlingRate",
            "params": {
                "rate": 10,
            },
            "id": 0,
        }
        ws.send(json.dumps(data))
        ws.recv()
        ws.close()
    finally:
        driver.quit()
