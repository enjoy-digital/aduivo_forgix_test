#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from host import forgix_gui


# Test Helpers -------------------------------------------------------------------------------------


class FakeReg:
    def __init__(self, address, value=0):
        self.addr   = address
        self.value  = value
        self.writes = []

    def read(self):
        return self.value

    def write(self, value):
        value &= 0xffffffff
        self.value = value
        self.writes.append(value)


class FakeBases:
    identifier_mem = 0x800


class FakeBus:
    def __init__(self, with_demo=False, with_leds=True, identifier="LiteX SoC on Adiuvo Forgix"):
        self.identifier = identifier
        self.bases = FakeBases()
        self.regs = type("FakeRegs", (), {})()
        self.regs.ctrl_scratch = FakeReg(0x0004, 0x5a5aa5a5)
        self.regs.ctrl_bus_errors = FakeReg(0x0008, 0)
        if with_leds:
            self.regs.leds_out = FakeReg(0x1000, 0)
        if with_demo:
            self.regs.demo_leds_mode = FakeReg(0x2000, 1)
            self.regs.demo_leds_rgb = FakeReg(0x2004, 7)
            self.regs.demo_leds_speed = FakeReg(0x2008, 8)
            self.regs.demo_leds_counter = FakeReg(0x200c, 0x42)

    def read(self, address):
        offset = address - self.bases.identifier_mem
        if offset >= 0 and offset % 4 == 0:
            index = offset // 4
            if index < len(self.identifier):
                return ord(self.identifier[index])
            if index == len(self.identifier):
                return 0
        return 0


# Tests --------------------------------------------------------------------------------------------


class ForgixGUITest(unittest.TestCase):
    def test_reads_identifier(self):
        bus = FakeBus(identifier="Forgix GUI Test")

        self.assertEqual(forgix_gui.read_identifier(bus), "Forgix GUI Test")

    def test_detects_base_capabilities(self):
        caps = forgix_gui.detect_capabilities(FakeBus())

        self.assertTrue(caps["identifier"])
        self.assertTrue(caps["scratch"])
        self.assertTrue(caps["bus_errors"])
        self.assertTrue(caps["leds"])
        self.assertFalse(caps["demo_core"])
        self.assertFalse(caps["demo_counter"])

    def test_detects_demo_capabilities(self):
        caps = forgix_gui.detect_capabilities(FakeBus(with_demo=True))

        self.assertTrue(caps["demo_core"])
        self.assertTrue(caps["demo_counter"])

    def test_scratch_roundtrip_restores_original_value(self):
        bus = FakeBus()
        original, readback = forgix_gui.scratch_roundtrip(bus, value=0x12345678)

        self.assertEqual(original, 0x5a5aa5a5)
        self.assertEqual(readback, 0x12345678)
        self.assertEqual(bus.regs.ctrl_scratch.value, original)

    def test_set_led_uses_base_led_csr(self):
        bus = FakeBus()

        self.assertTrue(forgix_gui.set_led(bus, 0x5))
        self.assertEqual(bus.regs.leds_out.writes, [0x5])

    def test_set_led_uses_demo_core_when_base_led_csr_is_absent(self):
        bus = FakeBus(with_demo=True, with_leds=False)

        self.assertTrue(forgix_gui.set_led(bus, 0x6))
        self.assertEqual(bus.regs.demo_leds_rgb.writes, [0x6])
        self.assertEqual(bus.regs.demo_leds_mode.writes, [0])

    def test_set_demo_writes_requested_fields(self):
        bus = FakeBus(with_demo=True)

        self.assertTrue(forgix_gui.set_demo(bus, mode=3, rgb=0x5, speed=12))

        self.assertEqual(bus.regs.demo_leds_mode.writes, [3])
        self.assertEqual(bus.regs.demo_leds_rgb.writes, [0x5])
        self.assertEqual(bus.regs.demo_leds_speed.writes, [12])

    def test_iter_registers_sorts_by_address(self):
        registers = forgix_gui.iter_registers(FakeBus(with_demo=True))

        self.assertEqual([name for _, name, _ in registers][:3], [
            "ctrl_scratch",
            "ctrl_bus_errors",
            "leds_out",
        ])


if __name__ == "__main__":
    unittest.main()
