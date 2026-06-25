#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import sys
import time

from fpga_loader import ForgixFPGALoader, default_bitstream
import test_forgix


# Run ----------------------------------------------------------------------------------------------


def main(path=None):
    if path is None:
        path = sys.argv[1] if len(sys.argv) > 1 else default_bitstream()

    print("Forgix LiteX load-and-test")
    print("Loading FPGA from %s:" % path)
    loader = ForgixFPGALoader()
    start = time.ticks_ms()
    written = loader.program(path)
    elapsed = time.ticks_diff(time.ticks_ms(), start)
    print("Programmed %u bytes in %u ms" % (written, elapsed))

    time.sleep_ms(50)
    test_forgix.main()


if __name__ == "__main__":
    main()
