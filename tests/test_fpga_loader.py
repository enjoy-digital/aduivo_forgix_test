#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import sys
import types
import tempfile
import unittest
from pathlib import Path

# MicroPython Stubs --------------------------------------------------------------------------------


machine = types.ModuleType("machine")


class Pin:
    IN      = 0
    OUT     = 1
    PULL_UP = 2

    def __init__(self, pin, mode=None, pull=None, value=0):
        self.pin    = pin
        self.mode   = mode
        self.pull   = pull
        self._value = value

    def value(self, value=None):
        if value is None:
            return self._value
        self._value = value


class SPI:
    MSB = 0

    def __init__(self, *args, **kwargs):
        self.args   = args
        self.kwargs = kwargs

    def write(self, data):
        pass

    def deinit(self):
        pass


machine.Pin = Pin
machine.SPI = SPI
sys.modules["machine"] = machine

from micropython import fpga_loader

# Tests --------------------------------------------------------------------------------------------


class FPGALoaderParserTest(unittest.TestCase):
    def test_default_pins_do_not_claim_miso(self):
        self.assertNotIn("miso", fpga_loader.DEFAULT_PINS)

    def test_plain_hex_chunks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.hex"
            bitstream.write_text("0a 0b\n0c 0d", encoding="utf-8")

            chunks = list(fpga_loader.iter_bitstream_chunks(str(bitstream), chunk_size=3))
            self.assertEqual(chunks, [
                bytearray(b"\x0a\x0b\x0c"),
                bytearray(b"\x0d"),
            ])

    def test_binary_chunks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.bin"
            bitstream.write_bytes(b"\x0a\x0b\x0c\x0d")

            chunks = list(fpga_loader.iter_bitstream_chunks(str(bitstream), chunk_size=3))
            self.assertEqual(chunks, [
                b"\x0a\x0b\x0c",
                b"\x0d",
            ])

    def test_intel_hex_chunks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.hex"
            bitstream.write_text(
                "\n".join([
                    ":0400000001020304F2",
                    ":00000001FF",
                    "",
                ]),
                encoding="utf-8",
            )

            chunks = list(fpga_loader.iter_bitstream_chunks(str(bitstream), chunk_size=3))
            self.assertEqual(chunks, [
                bytearray(b"\x01\x02\x03"),
                bytearray(b"\x04"),
            ])

    def test_intel_hex_gap_is_filled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.hex"
            bitstream.write_text(
                "\n".join([
                    ":020000000102FB",
                    ":020004000304F3",
                    ":00000001FF",
                    "",
                ]),
                encoding="utf-8",
            )

            chunks = list(fpga_loader.iter_bitstream_chunks(str(bitstream), chunk_size=8))
            self.assertEqual(chunks, [
                bytearray(b"\x01\x02\xff\xff\x03\x04"),
            ])

    def test_rejects_bad_checksum(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.hex"
            bitstream.write_text(":040000000102030400\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                list(fpga_loader.iter_bitstream_chunks(str(bitstream)))

    def test_status_low_is_fatal(self):
        class StatusLowLoader(fpga_loader.ForgixFPGALoader):
            def __init__(self):
                super().__init__()
                self.aborted = False

            def begin(self):
                self.spi = types.SimpleNamespace(write=lambda data: None)

            def finish(self):
                return {"done" : 1, "status" : 0}

            def abort(self):
                self.aborted = True

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp_dir:
            bitstream = Path(tmp_dir) / "adiuvo_forgix.hex"
            bitstream.write_text("0a", encoding="utf-8")

            loader = StatusLowLoader()
            with self.assertRaises(OSError):
                loader.program(str(bitstream), progress=False)
            self.assertTrue(loader.aborted)


if __name__ == "__main__":
    unittest.main()
