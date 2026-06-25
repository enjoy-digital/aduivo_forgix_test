#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import tempfile
import unittest
from pathlib import Path

from tools import bitstream2bin


# Tests --------------------------------------------------------------------------------------------


class Bitstream2BinTest(unittest.TestCase):
    def test_plain_hex_conversion(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.hex"
            output = Path(tmp_dir) / "adiuvo_forgix.bin"
            bitstream.write_text("0a\n0b\n0c\n0d\n", encoding="utf-8")

            written = bitstream2bin.convert(bitstream, output)
            self.assertEqual(written, 4)
            self.assertEqual(output.read_bytes(), b"\x0a\x0b\x0c\x0d")

    def test_intel_hex_conversion(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.hex"
            output = Path(tmp_dir) / "adiuvo_forgix.bin"
            bitstream.write_text(
                "\n".join([
                    ":020000000102FB",
                    ":020004000304F3",
                    ":00000001FF",
                    "",
                ]),
                encoding="utf-8",
            )

            written = bitstream2bin.convert(bitstream, output)
            self.assertEqual(written, 6)
            self.assertEqual(output.read_bytes(), b"\x01\x02\xff\xff\x03\x04")


if __name__ == "__main__":
    unittest.main()
