#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import contextlib
import io
import unittest

from micropython import csr
from micropython import demo_forgix


# Test Helpers -------------------------------------------------------------------------------------


class FakeBus:
    def __init__(self, identifier="LiteX SoC on Adiuvo Forgix"):
        self.identifier = identifier
        self.registers = {
            csr.CSR_CTRL_SCRATCH: 0x5a5aa5a5,
        }
        self.writes = []

    def read(self, address):
        offset = address - csr.CSR_BASE_IDENTIFIER_MEM
        if offset >= 0 and offset % 4 == 0:
            index = offset // 4
            if index < len(self.identifier):
                return ord(self.identifier[index])
            if index == len(self.identifier):
                return 0
        return self.registers.get(address, 0)

    def write(self, address, value):
        self.registers[address] = value
        self.writes.append((address, value))

    def writes_to(self, address):
        return [value for written_address, value in self.writes if written_address == address]


class CSRAttributeMixin:
    def set_csr_attr(self, name, value):
        sentinel = object()
        previous = getattr(csr, name, sentinel)
        setattr(csr, name, value)

        def restore():
            if previous is sentinel:
                delattr(csr, name)
            else:
                setattr(csr, name, previous)

        self.addCleanup(restore)

    def remove_csr_attr(self, name):
        sentinel = object()
        previous = getattr(csr, name, sentinel)
        if previous is not sentinel:
            delattr(csr, name)

        def restore():
            if previous is not sentinel:
                setattr(csr, name, previous)

        self.addCleanup(restore)


# Tests --------------------------------------------------------------------------------------------


class DemoForgixTest(CSRAttributeMixin, unittest.TestCase):
    def quietly(self, fn, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*args, **kwargs)

    def test_led_sequence_turns_leds_off(self):
        bus = FakeBus()

        demo_forgix.led_sequence(
            bus,
            (demo_forgix.LED_RED, demo_forgix.LED_GREEN),
            delay_ms=0,
            echo=False,
        )

        self.assertEqual(bus.writes_to(csr.CSR_LEDS_OUT), [
            demo_forgix.LED_RED,
            demo_forgix.LED_GREEN,
            demo_forgix.LED_OFF,
        ])

    def test_quick_demo_restores_scratch_and_leds(self):
        bus = FakeBus()
        original = bus.registers[csr.CSR_CTRL_SCRATCH]

        self.quietly(demo_forgix.quick_demo, bus=bus, delay_ms=0)

        self.assertEqual(bus.registers[csr.CSR_CTRL_SCRATCH], original)
        self.assertEqual(bus.writes_to(csr.CSR_LEDS_OUT)[-1], demo_forgix.LED_OFF)

    def test_stress_demo_restores_scratch_and_leds(self):
        bus = FakeBus()
        original = bus.registers[csr.CSR_CTRL_SCRATCH]

        self.quietly(demo_forgix.stress_demo, bus=bus, cycles=1, delay_ms=0)

        self.assertEqual(bus.registers[csr.CSR_CTRL_SCRATCH], original)
        self.assertEqual(bus.writes_to(csr.CSR_LEDS_OUT)[-1], demo_forgix.LED_OFF)

    def test_hardware_demo_core_detection_and_writes(self):
        self.set_csr_attr("CSR_DEMO_LEDS_MODE",    0x2000)
        self.set_csr_attr("CSR_DEMO_LEDS_RGB",     0x2004)
        self.set_csr_attr("CSR_DEMO_LEDS_SPEED",   0x2008)
        self.set_csr_attr("CSR_DEMO_LEDS_COUNTER", 0x200c)
        bus = FakeBus()
        bus.registers[0x200c] = 0x42

        handled = self.quietly(demo_forgix.hardware_show, bus, cycles=1, delay_ms=0)

        self.assertTrue(handled)
        self.assertGreater(len(bus.writes_to(0x2000)), 0)
        self.assertGreater(len(bus.writes_to(0x2004)), 0)
        self.assertGreater(len(bus.writes_to(0x2008)), 0)

    def test_led_sequence_uses_demo_core_when_leds_csr_is_absent(self):
        self.remove_csr_attr("CSR_LEDS_OUT")
        self.set_csr_attr("CSR_DEMO_LEDS_MODE",  0x2000)
        self.set_csr_attr("CSR_DEMO_LEDS_RGB",   0x2004)
        self.set_csr_attr("CSR_DEMO_LEDS_SPEED", 0x2008)
        bus = FakeBus()

        demo_forgix.led_sequence(
            bus,
            (demo_forgix.LED_RED, demo_forgix.LED_GREEN),
            delay_ms=0,
            echo=False,
        )

        self.assertEqual(bus.writes_to(0x2004), [
            demo_forgix.LED_RED,
            demo_forgix.LED_GREEN,
            demo_forgix.LED_OFF,
        ])
        self.assertEqual(bus.writes_to(0x2000), [0, 0, 0])

    def test_main_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            demo_forgix.main("unknown", bus=FakeBus())


if __name__ == "__main__":
    unittest.main()
