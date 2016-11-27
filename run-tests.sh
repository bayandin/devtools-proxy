#!/usr/bin/env bash

if [[ $# -eq 0 ]] ; then
    echo >&2 "No arguments"
    exit 1
elif [[ $# -gt 1 ]] ; then
    echo >&2 "Too many arguments: ${@:1}"
    exit 1
fi

case "$1" in
    functional)
        readonly TESTS="functional"
        ;;
    integration)
        readonly TESTS="integration"
        ;;
    compatibility)
        readonly TESTS="compatibility/selenium"
        ;;
    *)
        echo >&2 "Unknown argument: $1 (functional|integration|compatibility)"
        exit 1
        ;;
esac

readonly PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
readonly CHROME_WRAPPER_PATH=${CHROME_WRAPPER_PATH:-"${PROJECT_DIR}/devtools/chrome-wrapper.sh"}
readonly DEVTOOLS_PROXY_PATH=${DEVTOOLS_PROXY_PATH:-"${PROJECT_DIR}/devtools/proxy.py"}
PYTEST_OPTIONS=(-n=auto --verbose --instafail)

if [[ ${TESTS} == "compatibility/selenium" ]]; then
    readonly WITH_DEVTOOLS_PROXY=${WITH_DEVTOOLS_PROXY:-true}
    readonly DEVTOOLS_PROXY_PATCH=$(cat ${PROJECT_DIR}/tests/compatibility/conftest.py.patch)
    # TODO: Remove PATCH after release of the next version of Selenium 3.0.2 or 3.1.0
    readonly PATCH=$(cat ${PROJECT_DIR}/tests/compatibility/2936.diff) # https://github.com/SeleniumHQ/selenium/pull/2936
    echo "$DEVTOOLS_PROXY_PATCH" | patch -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium"
    echo "$PATCH" | patch -N -p4 -d "${PROJECT_DIR}/tests/compatibility/selenium" py/test/selenium/webdriver/common/network.py
    PYTEST_OPTIONS+=(--driver=Chrome)
fi

py.test  ${PYTEST_OPTIONS[@]} "${PROJECT_DIR}/tests/${TESTS}/"
EXIT_CODE=$?

if [[ ${TESTS} == "compatibility/selenium" ]]; then
    echo "$PATCH" | patch -R -N -p4 -d "${PROJECT_DIR}/tests/compatibility/selenium" py/test/selenium/webdriver/common/network.py
    echo "$DEVTOOLS_PROXY_PATCH" | patch -R -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium"
fi

exit ${EXIT_CODE}
