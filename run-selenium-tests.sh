#!/usr/bin/env bash

readonly PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
readonly CHROME_WRAPPER_PATH=${CHROME_WRAPPER_PATH:-"${PROJECT_DIR}/devtools/chrome-wrapper.sh"}
readonly DEVTOOLS_PROXY_PATH=${DEVTOOLS_PROXY_PATH:-"${PROJECT_DIR}/devtools/proxy.py"}
readonly DEVTOOLS_PROXY=${DEVTOOLS_PROXY:-true}
readonly DEVTOOLS_PROXY_PATCH=$(cat ${PROJECT_DIR}/tests/compatibility/conftest.py.patch)
# TODO: Remove PATCH after release of the next version of Selenium 3.0.2 or 3.1.0
readonly PATCH=$(curl https://patch-diff.githubusercontent.com/raw/SeleniumHQ/selenium/pull/2936.diff)

echo "$DEVTOOLS_PROXY_PATCH" | patch -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium"
echo "$PATCH" | patch -N -p4 -d "${PROJECT_DIR}/tests/compatibility/selenium" py/test/selenium/webdriver/common/network.py
rm -rf "${PROJECT_DIR}/.cache/"

py.test -n=auto --driver=Chrome "${PROJECT_DIR}/tests/compatibility/selenium/"
EXIT_CODE=$?

# TODO: Remove rerunning after release of the next version of Selenium 3.0.2 or 3.1.0
if [ -n "${CI}" ] && [ "${EXIT_CODE}" != "0" ]; then
    py.test -n=auto --driver=Chrome --verbose --instafail --last-failed "${PROJECT_DIR}/tests/compatibility/selenium"
    EXIT_CODE=$?
fi

echo "$PATCH" | patch -R -N -p4 -d "${PROJECT_DIR}/tests/compatibility/selenium" py/test/selenium/webdriver/common/network.py
echo "$DEVTOOLS_PROXY_PATCH" | patch -R -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium"

exit ${EXIT_CODE}
