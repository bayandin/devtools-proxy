#!/usr/bin/env bash

function watch_dog {
    local PID=$1
    local PROXY_PID=$2
    while true; do
        if ! kill -0 ${PID}; then
            kill ${PROXY_PID}
            break
        fi
        sleep 1
    done
}

CLI_PARAMS=$@

DEV_TOOLS_PROXY_BINARY_RE="--devtools-proxy-binary=([^[:space:]]+)"
if [[ ${CLI_PARAMS} =~ ${DEV_TOOLS_PROXY_BINARY_RE} ]]; then
    DEV_TOOLS_BINARY=${BASH_REMATCH[1]}
fi

DEV_TOOLS_PROXY_LOG_FILE_RE="--devtools-proxy-log-file=([^[:space:]]+)"
if [[ ${CLI_PARAMS} =~ ${DEV_TOOLS_PROXY_LOG_FILE_RE} ]]; then
    DEV_TOOLS_PROXY_LOG_FILE=${BASH_REMATCH[1]}
fi

if [ -z "$DEV_TOOLS_PROXY_LOG_FILE" ]; then
    DEV_TOOLS_PROXY_LOG_FILE=/dev/null
fi

if [ -n "$DEV_TOOLS_BINARY" ]; then
    CHROME_DEBUGGING_PORT=9222
    PROXY_DEBUGGING_PORT="--remote-debugging-port=([[:digit:]]+)"
    if [[ ${CLI_PARAMS} =~ ${PROXY_DEBUGGING_PORT} ]]; then
        PROXY_DEBUGGING_PORT=${BASH_REMATCH[1]}
    fi
    CLI_PARAMS=${CLI_PARAMS//--remote-debugging-port=${PROXY_DEBUGGING_PORT}/--remote-debugging-port=${CHROME_DEBUGGING_PORT}}

    ${DEV_TOOLS_BINARY} ${PROXY_DEBUGGING_PORT} > ${DEV_TOOLS_PROXY_LOG_FILE} 2>&1 &

    PROXY_PID=$!
    CURRENT_PID=$$
    ( > /dev/null 2>&1 < /dev/null watch_dog ${CURRENT_PID} ${PROXY_PID} & ) &
fi

KERNEL_NAME=$(uname --kernel-name)
if [ ${KERNEL_NAME} == 'Linux' ]; then
    CHROME_BINARY="/opt/google/chrome/google-chrome"
elif [ ${KERNEL_NAME} == 'Darwin' ]; then
    CHROME_BINARY="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
else
    echo "Unknown or unsupported OS: '${KERNEL_NAME}'" >&2
    exit 1
fi

exec -a "$0" "${CHROME_BINARY}" ${CLI_PARAMS}
