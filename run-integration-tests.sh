#!/usr/bin/env bash

readonly PROJECT_DIR="$(dirname "$(readlink -f "$0")")"

py.test -n=auto --verbose --instafail ${PROJECT_DIR}/tests/integration
