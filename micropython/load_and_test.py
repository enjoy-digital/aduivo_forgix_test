#
# This file is part of Adiuvo Forgix LiteX Test.
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
import time

from fpga_loader import ForgixFPGALoader
import test_forgix


def main(path=None):
    if path is None:
        path = sys.argv[1] if len(sys.argv) > 1 else "adiuvo_forgix.hex"

    print("Forgix LiteX load-and-test")
    print("Loading FPGA:")
    loader = ForgixFPGALoader()
    written = loader.program(path)
    print("Programmed %u bytes" % written)

    time.sleep_ms(50)
    test_forgix.main()


if __name__ == "__main__":
    main()
