#!/usr/bin/env sh
set -eu

TARGET=adiuvo_forgix
OUTPUT_DIR=${OUTPUT_DIR:-build/${TARGET}}
BITSTREAM=${1:-${OUTPUT_DIR}/gateware/outflow/${TARGET}.hex}
SPI_HZ=${FORGIX_SPI_HZ:-8000000}

if [ -z "${FORGE_LOADER_HOST:-}" ]; then
    echo "Set FORGE_LOADER_HOST to the Forgix BitStream_Loader/host directory." >&2
    exit 1
fi

if [ -z "${FORGIX_PORT:-}" ]; then
    echo "Set FORGIX_PORT to the RP2350 USB CDC port, for example /dev/ttyACM0 or COM7." >&2
    exit 1
fi

PYTHONPATH="${FORGE_LOADER_HOST}${PYTHONPATH:+:${PYTHONPATH}}" \
    python3 -m forge_loader.cli \
        --port "${FORGIX_PORT}" \
        --file "${BITSTREAM}" \
        --spi-hz "${SPI_HZ}"
