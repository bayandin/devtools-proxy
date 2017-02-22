#!/usr/bin/env bash

# Building standalone binary for Linux on macOS:
# docker run --volume $(pwd):/build --workdir /build python:3.6.0 /build/build-standalone.sh

readonly PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
readonly PLATFORM=$(python3 -c "import sys; print(sys.platform)")
readonly VERSION=$(python3 -c "from devtools import __version__; print(__version__)")

pip3 install -U pip
pip3 install -Ur requirements-build.txt
pyinstaller --name devtools-proxy --clean --onefile --distpath ${PROJECT_DIR}/dist/${PLATFORM} ${PROJECT_DIR}/devtools/proxy.py

tar -zcvf ${PROJECT_DIR}/dist/devtools-proxy-${PLATFORM}-${VERSION}.tgz \
    -C ${PROJECT_DIR}/dist/${PLATFORM} devtools-proxy \
    -C ${PROJECT_DIR}/devtools chrome-wrapper.sh
