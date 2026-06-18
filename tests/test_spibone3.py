#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import sys
import types
import unittest

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


machine.Pin = Pin
sys.modules["machine"] = machine

from micropython.spibone3 import SPIBone3Wire

# Tests --------------------------------------------------------------------------------------------


class SPIBone3WireTest(unittest.TestCase):
    def test_deselect_releases_shared_data_pin(self):
        bus = SPIBone3Wire(half_period_us=0)

        bus._drive_data(0)
        bus._deselect()

        self.assertEqual(bus.cs_n.value(), 1)
        self.assertEqual(bus.clk.value(), 0)
        self.assertEqual(bus.data.mode, Pin.IN)
        self.assertEqual(bus.data.pull, Pin.PULL_UP)


if __name__ == "__main__":
    unittest.main()
