#!/usr/bin/env bash

function watch_dog {
    local CHROME_PID=$1
    local PROXY_PID=$2
    while true; do
        if ! kill -0 ${CHROME_PID}; then
            kill ${PROXY_PID}
            break
        fi
        sleep 1
    done
}

DEV_TOOLS_PROXY_BINARY_RE="--devtools-proxy-binary=(.+)"
PROXY_DEBUGGING_PORT_RE="--remote-debugging-port=([[:digit:]]+)"

KNOWN_PORT=9222
KNOWN_PORT_RE="--devtools-proxy-port=([[:digit:]]+)"

CHROME_DEBUGGING_PORT=12222
CHROME_DEBUGGING_PORT_RE="--devtools-proxy-chrome-debugging-port=([[:digit:]]+)"

DEV_TOOLS_PROXY_LOG_FILE=/dev/null
DEV_TOOLS_PROXY_LOG_FILE_RE="--devtools-proxy-log-file=(.+)"

declare -a CLI_PARAMS=("$@")

for i in ${!CLI_PARAMS[@]}; do
    VALUE=${CLI_PARAMS[$i]}
    if [[ ${VALUE} =~ ${PROXY_DEBUGGING_PORT_RE} ]]; then
        PROXY_DEBUGGING_PORT=${BASH_REMATCH[1]}
        PROXY_DEBUGGING_PORT_IDX=${i}
    elif [[ ${VALUE} =~ ${DEV_TOOLS_PROXY_BINARY_RE} ]]; then
        DEV_TOOLS_PROXY_BINARY=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${DEV_TOOLS_PROXY_LOG_FILE_RE} ]]; then
        DEV_TOOLS_PROXY_LOG_FILE=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${KNOWN_PORT_RE} ]]; then
        KNOWN_PORT=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${CHROME_DEBUGGING_PORT_RE} ]]; then
        CHROME_DEBUGGING_PORT=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    fi
done

if [ -n "$DEV_TOOLS_PROXY_BINARY" ]; then
    CLI_PARAMS[$PROXY_DEBUGGING_PORT_IDX]="--remote-debugging-port=${CHROME_DEBUGGING_PORT}"

    ${DEV_TOOLS_PROXY_BINARY} --port ${KNOWN_PORT} ${PROXY_DEBUGGING_PORT} > ${DEV_TOOLS_PROXY_LOG_FILE} 2>&1 &
    PROXY_PID=$!
    CHROME_PID=$$
    ( > /dev/null 2>&1 < /dev/null watch_dog ${CHROME_PID} ${PROXY_PID} & ) &
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

exec -a "$0" "${CHROME_BINARY}" "${CLI_PARAMS[@]}"
