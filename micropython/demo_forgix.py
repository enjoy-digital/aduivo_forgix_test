#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import sys
import time

try:
    import csr
except ImportError:
    from micropython import csr

try:
    from spibone3 import SPIBone3Wire, read_identifier
except ImportError:
    try:
        from micropython.spibone3 import SPIBone3Wire, read_identifier
    except ImportError:
        SPIBone3Wire = None

        def read_identifier(bus, base, max_chars=256):
            chars = []
            for i in range(max_chars):
                value = bus.read(base + 4*i) & 0xff
                if value == 0:
                    break
                chars.append(chr(value))
            return "".join(chars)

# LED Colors ---------------------------------------------------------------------------------------


LED_OFF     = 0x0
LED_RED     = 0x1
LED_GREEN   = 0x2
LED_YELLOW  = 0x3
LED_BLUE    = 0x4
LED_MAGENTA = 0x5
LED_CYAN    = 0x6
LED_WHITE   = 0x7

COLOR_SEQUENCE = (
    LED_RED,
    LED_GREEN,
    LED_BLUE,
    LED_YELLOW,
    LED_CYAN,
    LED_MAGENTA,
    LED_WHITE,
)

DEMO_MODES = ("quick", "show", "stress")
DEMO_CORE_REGS = (
    "CSR_DEMO_LEDS_MODE",
    "CSR_DEMO_LEDS_RGB",
    "CSR_DEMO_LEDS_SPEED",
)

# Helpers ------------------------------------------------------------------------------------------


def _sleep_ms(delay_ms):
    if delay_ms <= 0:
        return
    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(delay_ms)
    else:
        time.sleep(delay_ms / 1000.0)


def _make_bus(bus=None):
    if bus is not None:
        return bus
    if SPIBone3Wire is None:
        raise RuntimeError("SPIBone3Wire is unavailable; pass an explicit bus")
    return SPIBone3Wire()


def _positive_int(value, default=1):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def write_led(bus, value):
    value &= 0x7
    if hasattr(csr, "CSR_LEDS_OUT"):
        bus.write(csr.CSR_LEDS_OUT, value)
    elif demo_core_available():
        bus.write(getattr(csr, "CSR_DEMO_LEDS_RGB"), value)
        bus.write(getattr(csr, "CSR_DEMO_LEDS_MODE"), 0)
    else:
        raise RuntimeError("no LED CSR is available")


def led_off(bus):
    write_led(bus, LED_OFF)


def led_sequence(bus, sequence, delay_ms=120, repeat=1, final=LED_OFF, echo=True):
    repeat = _positive_int(repeat)
    for _ in range(repeat):
        for value in sequence:
            if echo:
                print("  leds_out = 0x%x" % value)
            write_led(bus, value)
            _sleep_ms(delay_ms)
    if final is not None:
        if echo:
            print("  leds_out = 0x%x" % final)
        write_led(bus, final)


def binary_count(bus, delay_ms=80, repeat=1, echo=True):
    led_sequence(bus, range(8), delay_ms=delay_ms, repeat=repeat, echo=echo)


def color_chase(bus, delay_ms=120, repeat=1, echo=True):
    led_sequence(bus, COLOR_SEQUENCE, delay_ms=delay_ms, repeat=repeat, echo=echo)


def software_pwm_fade(bus, color=LED_WHITE, steps=8, frame_ms=24, repeat=1):
    steps = _positive_int(steps, default=8)
    repeat = _positive_int(repeat)
    levels = list(range(steps + 1)) + list(range(steps - 1, -1, -1))
    for _ in range(repeat):
        for level in levels:
            on_ms = (frame_ms * level) // steps
            off_ms = frame_ms - on_ms
            if on_ms:
                write_led(bus, color)
                _sleep_ms(on_ms)
            if off_ms:
                write_led(bus, LED_OFF)
                _sleep_ms(off_ms)
    led_off(bus)


def scratch_roundtrip(bus, values=(0x12345678, 0xa5a55a5a)):
    original = bus.read(csr.CSR_CTRL_SCRATCH)
    print("Scratch CSR:")
    print("  original: 0x%08x" % original)
    try:
        for value in values:
            bus.write(csr.CSR_CTRL_SCRATCH, value)
            readback = bus.read(csr.CSR_CTRL_SCRATCH)
            print("  write/read: 0x%08x / 0x%08x" % (value, readback))
            if readback != value:
                raise RuntimeError("scratch CSR readback mismatch")
    finally:
        bus.write(csr.CSR_CTRL_SCRATCH, original)
    return original

# Optional Hardware Demo Core ----------------------------------------------------------------------


def demo_core_available():
    return all(hasattr(csr, name) for name in DEMO_CORE_REGS)


def hardware_show(bus, cycles=1, delay_ms=600):
    if not demo_core_available():
        return False

    print("Hardware LED demo core:")
    mode_reg  = getattr(csr, "CSR_DEMO_LEDS_MODE")
    rgb_reg   = getattr(csr, "CSR_DEMO_LEDS_RGB")
    speed_reg = getattr(csr, "CSR_DEMO_LEDS_SPEED")
    counter_reg = getattr(csr, "CSR_DEMO_LEDS_COUNTER", None)

    sequence = (
        (1, LED_WHITE, 8),
        (2, LED_RED,   5),
        (2, LED_GREEN, 5),
        (2, LED_BLUE,  5),
        (3, LED_CYAN,  3),
    )
    for _ in range(_positive_int(cycles)):
        for mode, rgb, speed in sequence:
            print("  mode=%u rgb=0x%x speed=%u" % (mode, rgb, speed))
            bus.write(rgb_reg, rgb)
            bus.write(speed_reg, speed)
            bus.write(mode_reg, mode)
            _sleep_ms(delay_ms)

    if counter_reg is not None:
        print("  counter=0x%08x" % bus.read(counter_reg))
    return True

# Demos --------------------------------------------------------------------------------------------


def quick_demo(bus=None, delay_ms=80):
    bus = _make_bus(bus)
    print("Forgix quick demo")
    print("Identifier:")
    print("  %s" % read_identifier(bus, csr.CSR_BASE_IDENTIFIER_MEM))
    scratch_roundtrip(bus, values=(0x12345678,))
    print("LED CSR:")
    led_sequence(bus, (LED_RED, LED_GREEN, LED_BLUE), delay_ms=delay_ms)
    print("Done")


def show_demo(bus=None, cycles=1, delay_ms=120):
    bus = _make_bus(bus)
    print("Forgix LED show")
    if hardware_show(bus, cycles=cycles):
        print("Done")
        return

    print("Software LED demo:")
    for _ in range(_positive_int(cycles)):
        print("  color chase")
        color_chase(bus, delay_ms=delay_ms, echo=False)
        print("  binary count")
        binary_count(bus, delay_ms=max(delay_ms // 2, 1), echo=False)
        print("  white fade")
        software_pwm_fade(bus, color=LED_WHITE, steps=6, frame_ms=24)
    led_off(bus)
    print("Done")


def stress_demo(bus=None, cycles=1, delay_ms=40):
    bus = _make_bus(bus)
    print("Forgix stress demo")
    try:
        for cycle in range(_positive_int(cycles)):
            print("Cycle %u:" % (cycle + 1))
            scratch_roundtrip(bus)
            binary_count(bus, delay_ms=delay_ms, echo=False)
            color_chase(bus, delay_ms=delay_ms, echo=False)
    finally:
        led_off(bus)
    print("Done")

# Run ----------------------------------------------------------------------------------------------


def main(mode="show", cycles=1, bus=None):
    if mode is None:
        mode = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cycles is None:
        cycles = sys.argv[2] if len(sys.argv) > 2 else 1

    mode = str(mode).lower()
    cycles = _positive_int(cycles)

    if mode == "quick":
        quick_demo(bus=bus)
    elif mode == "show":
        show_demo(bus=bus, cycles=cycles)
    elif mode == "stress":
        stress_demo(bus=bus, cycles=cycles)
    else:
        raise ValueError("unknown demo mode: %s (expected quick, show or stress)" % mode)


if __name__ == "__main__":
    main(None, None)
