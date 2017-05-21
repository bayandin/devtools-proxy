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
        readonly TESTS="compatibility/selenium/py"
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

if [[ ${TESTS} == "compatibility/selenium/py" ]]; then
    readonly WITH_DEVTOOLS_PROXY=${WITH_DEVTOOLS_PROXY:-true}
    readonly DEVTOOLS_PROXY_PATCH=$(cat ${PROJECT_DIR}/tests/compatibility/conftest.py.patch)
    echo "$DEVTOOLS_PROXY_PATCH" | patch -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium/py"
    cp "${PROJECT_DIR}/tests/compatibility/getAttribute.js" "${PROJECT_DIR}/tests/compatibility/selenium/py/selenium/webdriver/remote/getAttribute.js"
    cp "${PROJECT_DIR}/tests/compatibility/isDisplayed.js" "${PROJECT_DIR}/tests/compatibility/selenium/py/selenium/webdriver/remote/isDisplayed.js"
    PYTEST_OPTIONS+=(--driver=Chrome --timeout-method=thread --timeout=120)
fi

py.test  ${PYTEST_OPTIONS[@]} "${PROJECT_DIR}/tests/${TESTS}/"
EXIT_CODE=$?

if [[ ${TESTS} == "compatibility/selenium/py" ]]; then
    echo "$DEVTOOLS_PROXY_PATCH" | patch -R -N -p0 -d "${PROJECT_DIR}/tests/compatibility/selenium/py"
    rm "${PROJECT_DIR}/tests/compatibility/selenium/py/selenium/webdriver/remote/getAttribute.js" "${PROJECT_DIR}/tests/compatibility/selenium/py/selenium/webdriver/remote/isDisplayed.js"
fi

exit ${EXIT_CODE}
