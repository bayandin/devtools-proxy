import json

from . import TestCase
from .utils import devtools_proxy_ws


class TestBasic(TestCase):
    def test_one_plus_one(self):
        data = {
            "id": 0,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "1 + 1",
            }
        }

        with devtools_proxy_ws(self.devtools_proxy_port) as ws:
            ws.send(json.dumps(data))
            raw_resp = ws.recv()

        resp = json.loads(raw_resp)
        assert 0 == resp['id']
        assert resp['result']['result']['type'] == 'number'
        assert resp['result']['result']['description'] == '2'
        assert resp['result']['result']['value'] == 2

    def test_two_clients(self):
        data1 = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "1 + 1",
            }
        }

        data2 = {
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "2 + 2",
            }
        }

        with devtools_proxy_ws(self.devtools_proxy_port) as ws1:
            with devtools_proxy_ws(self.devtools_proxy_port) as ws2:
                ws1.send(json.dumps(data1))
                ws2.send(json.dumps(data2))

                raw_resp1 = ws1.recv()
                raw_resp2 = ws2.recv()

        resp1 = json.loads(raw_resp1)
        assert resp1['id'] == 1
        assert resp1['result']['result']['value'] == 2

        resp2 = json.loads(raw_resp2)
        assert resp2['id'] == 2
        assert resp2['result']['result']['value'] == 4
