import selenium
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from tests import CHROME_WRAPPER_PATH, DEVTOOLS_PROXY_PATH
from tests.utils import free_port


class TestCase(object):
    def setup_method(self):
        self.devtools_proxy_port = free_port()

        capabilities = DesiredCapabilities.CHROME.copy()
        capabilities['chromeOptions'] = {
            'binary': CHROME_WRAPPER_PATH,
            'args': [
                '--devtools-proxy-binary={}'.format(DEVTOOLS_PROXY_PATH),
                '--devtools-proxy-chrome-debugging-port={}'.format(free_port()),
                '--devtools-proxy-args=--port {}'.format(self.devtools_proxy_port),
            ],
        }

        self.driver = selenium.webdriver.Chrome(desired_capabilities=capabilities)

    def teardown_method(self):
        self.driver.quit()
