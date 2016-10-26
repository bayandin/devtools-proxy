from pathlib import Path

import selenium
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from .utils import free_port

PROJECT_DIR = Path(__file__, '../../../').resolve()


class TestCase(object):
    def setup_method(self):
        self.devtools_proxy_port = free_port()

        capabilities = DesiredCapabilities.CHROME.copy()
        capabilities['chromeOptions'] = {
            'binary': '{}/chrome-wrapper.sh'.format(PROJECT_DIR),
            'args': [
                '--devtools-proxy-binary={}/devtools-proxy.py'.format(PROJECT_DIR),
                '--devtools-proxy-port={}'.format(self.devtools_proxy_port),
                '--devtools-proxy-chrome-debugging-port={}'.format(free_port())
            ],
        }

        self.driver = selenium.webdriver.Chrome(desired_capabilities=capabilities)

    def teardown_method(self):
        self.driver.quit()
