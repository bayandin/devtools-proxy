#!/usr/bin/env python3

import re

import requests
import selenium
from devtools.proxy import CHROME_WRAPPER_PATH
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait


def find_element(driver, locator):
    return WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located(locator))


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
        version = requests.get(f'http://localhost:{devtools_proxy_port}/json/version').json()
        webkit_version = version['WebKit-Version']  # 537.36 (@8ee402c67ff2f8f7c746e56d3530b4dcec0709ad)
        webkit_hash = re.search(r'\((.+)\)', webkit_version).group(1)  # @8ee402c67ff2f8f7c746e56d3530b4dcec0709ad

        tabs = requests.get(f'http://localhost:{devtools_proxy_port}/json/list').json()
        tab = next(tab for tab in tabs if tab.get('type') == 'page')
        devtools_frontend_url = tab['devtoolsFrontendUrl']
        devtools_frontend_url = re.sub(r'^/devtools/', '', devtools_frontend_url)

        url_template = 'https://chrome-devtools-frontend.appspot.com/serve_file/{}/{}&remoteFrontend=true'
        url = url_template.format(webkit_hash, devtools_frontend_url)
        print(url)

        driver.get('https://google.co.uk')
        find_element(driver, (By.CSS_SELECTOR, '[name = "q"]')).send_keys('ChromeDriver')
        find_element(driver, (By.CSS_SELECTOR, 'h3 > a')).click()  # The first one search result
        find_element(driver, (By.XPATH, '//a[text() = "Capabilities & ChromeOptions"]')).click()
        find_element(driver, (By.XPATH, '//h3//code[text() = "chromeOptions"]')).location_once_scrolled_into_view
    finally:
        driver.quit()
