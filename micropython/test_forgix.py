#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import time

import csr
from spibone3 import SPIBone3Wire, read_identifier

# Tests --------------------------------------------------------------------------------------------


def scratch_test(bus):
    print("Scratch CSR:")
    original = bus.read(csr.CSR_CTRL_SCRATCH)
    print("  original: 0x%08x" % original)
    for value in (0x12345678, 0xa5a55a5a, original):
        bus.write(csr.CSR_CTRL_SCRATCH, value)
        readback = bus.read(csr.CSR_CTRL_SCRATCH)
        print("  write/read: 0x%08x / 0x%08x" % (value, readback))
        if readback != value:
            raise RuntimeError("scratch CSR readback mismatch")


def leds_test(bus):
    print("LED CSR:")
    sequence = [0x0, 0x1, 0x2, 0x4, 0x7, 0x0, 0x7, 0x0]
    for value in sequence:
        print("  leds_out = 0x%x" % value)
        bus.write(csr.CSR_LEDS_OUT, value)
        time.sleep_ms(200)

# Run ----------------------------------------------------------------------------------------------


def main():
    print("Forgix LiteX SPIBone test")
    bus = SPIBone3Wire()

    identifier = read_identifier(bus, csr.CSR_BASE_IDENTIFIER_MEM)
    print("Identifier:")
    print("  %s" % identifier)

    scratch_test(bus)
    leds_test(bus)
    print("Done")


if __name__ == "__main__":
    main()
