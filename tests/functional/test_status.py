import requests

from tests.functional import TestCase
from tests.utils import devtools_proxy, free_port


class TestBasic(TestCase):
    def test_status_proxy_ports(self):
        port = free_port()

        with devtools_proxy(args=['--port', port]):
            status = requests.get('http://127.0.0.1:{}/status.json'.format(port)).json()

        assert status['proxy_ports'] == [port]
