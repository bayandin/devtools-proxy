#!/usr/bin/env bash

readonly PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
readonly CHROME_WRAPPER="${PROJECT_DIR}/chrome-wrapper.sh"
readonly PROXY_EXECUTABLE="${PROJECT_DIR}/devtools-proxy.py"
readonly DEBUG_DIR="${PROJECT_DIR}/.debug"
readonly DEVTOOLS_PROXY=${DEVTOOLS_PROXY:-true}
DEBUG=${DEBUG:-false}
# TODO: Remove PATCH after release of the next version of Selenium 3.0.2 or 3.1.0
readonly PATCH=$(curl https://patch-diff.githubusercontent.com/raw/SeleniumHQ/selenium/pull/2936.diff)
readonly DEVTOOLS_PROXY_ON_PATCH=$(cat <<-END
--- conftest.py
+++ conftest.py
@@ -15,6 +15,7 @@
 # specific language governing permissions and limitations
 # under the License.

+import os
 import socket
 import subprocess
 import time
@@ -25,6 +26,8 @@ import pytest
 from selenium import webdriver
 from selenium.webdriver import DesiredCapabilities

+from selenium.webdriver.common.utils import free_port
+
 drivers = (
     'BlackBerry',
     'Chrome',
@@ -67,6 +70,27 @@ def driver(request):
         reason = skip.kwargs.get('reason') or skip.name
         pytest.skip(reason)

+    if driver_class == 'Chrome':
+        debug = os.environ.get('DEBUG') == 'true'
+        devtools_proxy = os.environ.get('DEVTOOLS_PROXY') == 'true'
+        port = free_port()
+        capabilities = DesiredCapabilities.CHROME.copy()
+        if devtools_proxy:
+            capabilities['chromeOptions'] = {
+                'binary': '${CHROME_WRAPPER}',
+                'args': [
+                    '--devtools-proxy-binary=${PROXY_EXECUTABLE}',
+                    '--devtools-proxy-chrome-debugging-port={}'.format(port),
+                ]
+            }
+        if debug:
+            kwargs['service_log_path'] = '${DEBUG_DIR}/chromedriver_{}.log'.format(port),
+            if devtools_proxy:
+                capabilities['chromeOptions']['args'].append(
+                    '--devtools-proxy-log-file=${DEBUG_DIR}/devtools-proxy_{}.log'.format(
+                        port)
+                )
+        kwargs['desired_capabilities'] = capabilities
     if driver_class == 'BlackBerry':
         kwargs.update({'device_password': 'password'})
     if driver_class == 'Firefox':
END
)
rm -rf "${PROJECT_DIR}/.cache/"

echo "$DEVTOOLS_PROXY_ON_PATCH" | patch -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium"
echo "$PATCH" | patch -N -p4 -d "${PROJECT_DIR}/tests/compatibility/selenium" py/test/selenium/webdriver/common/network.py

py.test -n=auto --driver=Chrome "${PROJECT_DIR}/tests/compatibility/selenium/"
EXIT_CODE=$?

if [ -n "${CI}" ] && [ "${EXIT_CODE}" != "0" ]; then
    rm -rf "${DEBUG_DIR}"
    mkdir -p "${DEBUG_DIR}"

    DEBUG=true py.test -n=auto --driver=Chrome --verbose --instafail --last-failed "${PROJECT_DIR}/tests/compatibility/selenium"
    EXIT_CODE=$?
fi

echo "$PATCH" | patch -R -N -p4 -d "${PROJECT_DIR}/tests/compatibility/selenium" py/test/selenium/webdriver/common/network.py
echo "$DEVTOOLS_PROXY_ON_PATCH" | patch -R -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium"

if [ -n "${CI}" ] && [ "${EXIT_CODE}" != "0" ]; then
    ls -al "${DEBUG_DIR}"
    find "${DEBUG_DIR}" -type f -print -exec cat {} \;
fi

exit ${EXIT_CODE}
