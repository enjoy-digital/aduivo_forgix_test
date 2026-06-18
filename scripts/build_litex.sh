#!/usr/bin/env sh
set -eu

TARGET=adiuvo_forgix
OUTPUT_DIR=${OUTPUT_DIR:-build/${TARGET}}

python3 -m litex_boards.targets.${TARGET} \
    --build \
    --with-spibone \
    --output-dir "${OUTPUT_DIR}" \
    "$@"

python3 tools/csr2py.py "${OUTPUT_DIR}/csr.csv" --output micropython/csr.py
