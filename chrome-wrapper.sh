#!/usr/bin/env bash

function find_binary {
    local KERNEL_NAME=$(uname --kernel-name)
    local FILE_PATH

    declare -a FILES
    declare -a PATHS

    if [ ${KERNEL_NAME} == 'Linux' ]; then
        # https://chromium.googlesource.com/chromium/src/+/2729e442b1172c5094503a03fe356c8580bb919d/chrome/test/chromedriver/chrome/chrome_finder.cc
        FILES=(google-chrome chrome chromium chromium-browser)
        PATHS=(/opt/google/chrome /usr/local/bin /usr/local/sbin /usr/bin /usr/sbin /bin /sbin)
    elif [ ${KERNEL_NAME} == 'Darwin' ]; then
        FILES=(
            Google\ Chrome.app/Contents/MacOS/Google\ Chrome
            Chromium.app/Contents/MacOS/Chromium
        )
        PATHS=(/Applications)
    else
        echo "Unknown or unsupported OS: '${KERNEL_NAME}'" >&2
        exit 1
    fi

    for file in "${FILES[@]}"; do
        for path in "${PATHS[@]}"; do
            FILE_PATH="${path}/${file}"
            if [ -e "${FILE_PATH}" ]; then
                echo -n "${FILE_PATH}"
                return
            fi
        done
    done
}

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

PROXY_DEBUGGING_PORT_RE="--remote-debugging-port=([[:digit:]]+)"
DEV_TOOLS_PROXY_BINARY_RE="--devtools-proxy-binary=(.+)"

CHROME_BINARY=""
CHROME_BINARY_RE="--chrome-binary=(.+)"

CHROME_DEBUGGING_PORT=12222
CHROME_DEBUGGING_PORT_RE="--devtools-proxy-chrome-debugging-port=([[:digit:]]+)"

DEV_TOOLS_PROXY_ARGS=""
DEV_TOOLS_PROXY_ARGS_RE="--devtools-proxy-args=(.+)"

DEV_TOOLS_PROXY_LOG_FILE=/dev/null
DEV_TOOLS_PROXY_LOG_FILE_RE="--devtools-proxy-log-file=(.+)"

KNOWN_PORT=""
KNOWN_PORT_RE="--devtools-proxy-port=([[:digit:]]+)"

declare -a CLI_PARAMS=("$@")

for i in ${!CLI_PARAMS[@]}; do
    VALUE=${CLI_PARAMS[$i]}
    if [[ ${VALUE} =~ ${PROXY_DEBUGGING_PORT_RE} ]]; then
        PROXY_DEBUGGING_PORT=${BASH_REMATCH[1]}
        PROXY_DEBUGGING_PORT_IDX=${i}
    elif [[ ${VALUE} =~ ${DEV_TOOLS_PROXY_BINARY_RE} ]]; then
        DEV_TOOLS_PROXY_BINARY=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${CHROME_BINARY_RE} ]]; then
        CHROME_BINARY=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${CHROME_DEBUGGING_PORT_RE} ]]; then
        CHROME_DEBUGGING_PORT=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${DEV_TOOLS_PROXY_ARGS_RE} ]]; then
        DEV_TOOLS_PROXY_ARGS=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${DEV_TOOLS_PROXY_LOG_FILE_RE} ]]; then
        DEV_TOOLS_PROXY_LOG_FILE=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    elif [[ ${VALUE} =~ ${KNOWN_PORT_RE} ]]; then
        KNOWN_PORT=${BASH_REMATCH[1]}
        unset CLI_PARAMS[${i}]
    fi
done

if [ -n "$DEV_TOOLS_PROXY_BINARY" ]; then
    CLI_PARAMS[$PROXY_DEBUGGING_PORT_IDX]="--remote-debugging-port=${CHROME_DEBUGGING_PORT}"

    PORTS="${KNOWN_PORT} ${PROXY_DEBUGGING_PORT}"
    ${DEV_TOOLS_PROXY_BINARY} --port ${PORTS} --chrome-port ${CHROME_DEBUGGING_PORT} ${DEV_TOOLS_PROXY_ARGS} > ${DEV_TOOLS_PROXY_LOG_FILE} 2>&1 &
    PROXY_PID=$!
    CHROME_PID=$$
    ( > /dev/null 2>&1 < /dev/null watch_dog ${CHROME_PID} ${PROXY_PID} & ) &
fi

CHROME_BINARY=${CHROME_BINARY:-$(find_binary)}
exec -a "$0" "${CHROME_BINARY}" "${CLI_PARAMS[@]}"
