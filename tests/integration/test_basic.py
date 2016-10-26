import json

from . import TestCase
from .utils import devtools_proxy_ws


class TestBasic(TestCase):
    def test_one_plus_one(self):
        data = {
            "id": 0,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "1+1",
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
