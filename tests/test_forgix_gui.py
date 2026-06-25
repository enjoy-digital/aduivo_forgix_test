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
    def __init__(self, with_demo=False, with_leds=True, with_scope=False, identifier="LiteX SoC on Adiuvo Forgix"):
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
            self.regs.demo_leds_pwm_r = FakeReg(0x2010, 255)
            self.regs.demo_leds_pwm_g = FakeReg(0x2014, 255)
            self.regs.demo_leds_pwm_b = FakeReg(0x2018, 255)
            self.regs.demo_leds_pwm_period = FakeReg(0x201c, 255)
            self.regs.demo_leds_pattern = FakeReg(0x2020, 0)
            self.regs.demo_leds_trigger = FakeReg(0x2024, 0)
            self.regs.demo_leds_gpio_mask = FakeReg(0x2028, 0)
            self.regs.demo_leds_gpio_value = FakeReg(0x202c, 0)
            self.regs.demo_leds_status = FakeReg(0x2030, 0x2a)
            self.regs.demo_leds_frame_counter = FakeReg(0x2034, 0x100)
            self.regs.demo_leds_event_counter = FakeReg(0x2038, 0x200)
        if with_scope:
            self.regs.analyzer_storage_enable = FakeReg(0x3000, 0)

    def read(self, address):
        offset = address - self.bases.identifier_mem
        if offset >= 0 and offset % 4 == 0:
            index = offset // 4
            if index < len(self.identifier):
                return ord(self.identifier[index])
            if index == len(self.identifier):
                return 0
        return 0


class FakeAnalyzer:
    def __init__(self, regs, name, config_csv=None, debug=False):
        self.regs = regs
        self.name = name
        self.config_csv = config_csv
        self.debug = debug
        self.group = None
        self.length = None
        self.subsampling = None
        self.trigger = None
        self.layouts = {
            0: [("led", 3), ("tick", 1)],
            1: [("cyc", 1), ("stb", 1), ("adr", 8)],
        }

    def configure_group(self, group):
        self.group = group

    def configure_subsampler(self, subsampling):
        self.subsampling = subsampling

    def configure_rle(self, enable):
        self.rle = enable

    def add_trigger(self, cond):
        self.trigger = cond

    def configure_trigger(self):
        self.trigger = {}

    def run(self, offset=0, length=None):
        self.offset = offset
        self.length = length

    def wait_done(self, delay=0.2):
        self.delay = delay

    def upload(self, max_samples=None):
        return [0x0, 0x1, 0x7, 0xf][:max_samples]


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
        self.assertTrue(caps["demo_pwm"])
        self.assertTrue(caps["demo_pattern"])
        self.assertTrue(caps["demo_gpio"])
        self.assertTrue(caps["demo_status"])

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

        self.assertTrue(forgix_gui.set_demo(bus, mode=5, rgb=0x5, speed=12))

        self.assertEqual(bus.regs.demo_leds_mode.writes, [5])
        self.assertEqual(bus.regs.demo_leds_rgb.writes, [0x5])
        self.assertEqual(bus.regs.demo_leds_speed.writes, [12])

    def test_set_demo_pwm_writes_requested_fields(self):
        bus = FakeBus(with_demo=True)

        self.assertTrue(forgix_gui.set_demo_pwm(bus, r=1, g=2, b=3, period=4))

        self.assertEqual(bus.regs.demo_leds_pwm_r.writes, [1])
        self.assertEqual(bus.regs.demo_leds_pwm_g.writes, [2])
        self.assertEqual(bus.regs.demo_leds_pwm_b.writes, [3])
        self.assertEqual(bus.regs.demo_leds_pwm_period.writes, [4])

    def test_set_demo_pattern_and_gpio(self):
        bus = FakeBus(with_demo=True)

        self.assertTrue(forgix_gui.set_demo_pattern(bus, pattern=9, trigger=True))
        self.assertTrue(forgix_gui.set_demo_gpio(bus, mask=0x3ffff, value=0x15555))

        self.assertEqual(bus.regs.demo_leds_pattern.writes, [9])
        self.assertEqual(bus.regs.demo_leds_trigger.writes, [1])
        self.assertEqual(bus.regs.demo_leds_gpio_mask.writes, [0x3ffff])
        self.assertEqual(bus.regs.demo_leds_gpio_value.writes, [0x15555])

    def test_read_demo_status(self):
        status = forgix_gui.read_demo_status(FakeBus(with_demo=True))

        self.assertEqual(status["status"], 0x2a)
        self.assertEqual(status["frame_counter"], 0x100)
        self.assertEqual(status["event_counter"], 0x200)

    def test_capture_litescope_uses_driver(self):
        bus = FakeBus(with_demo=True, with_scope=True)

        analyzer, samples = forgix_gui.capture_litescope(
            bus,
            analyzer_csv = "analyzer.csv",
            group        = 1,
            length       = 3,
            subsampling  = 2,
            trigger      = {"cyc": "1"},
            driver_cls   = FakeAnalyzer,
        )

        self.assertEqual(analyzer.group, 1)
        self.assertEqual(analyzer.length, 3)
        self.assertEqual(analyzer.subsampling, 2)
        self.assertEqual(analyzer.trigger, {"cyc": "1"})
        self.assertEqual(samples, [0x0, 0x1, 0x7])

    def test_waveform_series_decodes_layout(self):
        series = forgix_gui.waveform_series([0b0000, 0b1011], [("led", 3), ("tick", 1)])

        self.assertEqual(series[0][0], "led")
        self.assertEqual(series[0][1], [0, 1])
        self.assertEqual(series[1][0], "tick")
        self.assertEqual(series[1][2], [1.0, 1.8])

    def test_iter_registers_sorts_by_address(self):
        registers = forgix_gui.iter_registers(FakeBus(with_demo=True))

        self.assertEqual([name for _, name, _ in registers][:3], [
            "ctrl_scratch",
            "ctrl_bus_errors",
            "leds_out",
        ])


if __name__ == "__main__":
    unittest.main()
