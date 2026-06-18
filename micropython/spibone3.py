#
# This file is part of Adiuvo Forgix LiteX Test.
#
# SPDX-License-Identifier: BSD-2-Clause

import time
from machine import Pin


DEFAULT_PINS = {
    "cs_n": 1,
    "clk":  2,
    "mosi": 3,
}


class SPIBone3Wire:
    def __init__(self, pins=None, half_period_us=1, timeout_bytes=256):
        if pins is None:
            pins = DEFAULT_PINS
        self.pin_mosi = pins["mosi"]
        self.cs_n = Pin(pins["cs_n"], Pin.OUT, value=1)
        self.clk  = Pin(pins["clk"],  Pin.OUT, value=0)
        self.data = Pin(self.pin_mosi, Pin.OUT, value=1)
        self.half_period_us = half_period_us
        self.timeout_bytes  = timeout_bytes

    def _delay(self):
        if self.half_period_us:
            time.sleep_us(self.half_period_us)

    def _drive_data(self, value=1):
        self.data = Pin(self.pin_mosi, Pin.OUT, value=value)

    def _release_data(self):
        self.data = Pin(self.pin_mosi, Pin.IN, Pin.PULL_UP)

    def _select(self):
        self.clk.value(0)
        self._drive_data(1)
        self.cs_n.value(0)
        self._delay()

    def _deselect(self):
        self.cs_n.value(1)
        self.clk.value(0)
        self._drive_data(1)
        self._delay()

    def _write_bit(self, value):
        self.data.value(1 if value else 0)
        self._delay()
        self.clk.value(1)
        self._delay()
        self.clk.value(0)
        self._delay()

    def _read_bit(self):
        self._delay()
        self.clk.value(1)
        self._delay()
        value = self.data.value()
        self.clk.value(0)
        self._delay()
        return value

    def _write_byte(self, value):
        for shift in range(7, -1, -1):
            self._write_bit((value >> shift) & 1)

    def _read_byte(self):
        value = 0
        for _ in range(8):
            value = (value << 1) | self._read_bit()
        return value

    def _write_u32(self, value):
        for shift in (24, 16, 8, 0):
            self._write_byte((value >> shift) & 0xff)

    def _read_u32(self):
        value = 0
        for _ in range(4):
            value = (value << 8) | self._read_byte()
        return value

    def _wait_response(self, expected):
        for _ in range(self.timeout_bytes):
            value = self._read_byte()
            if value == expected:
                return value
        raise OSError("SPIBone timeout waiting for 0x%02x" % expected)

    def read(self, address):
        self._select()
        try:
            self._write_byte(0x01)
            self._write_u32(address)
            self._release_data()
            self._wait_response(0x01)
            return self._read_u32()
        finally:
            self._deselect()

    def write(self, address, value):
        self._select()
        try:
            self._write_byte(0x00)
            self._write_u32(address)
            self._write_u32(value)
            self._release_data()
            self._wait_response(0x00)
        finally:
            self._deselect()


def read_identifier(bus, base, max_chars=256):
    chars = []
    for i in range(max_chars):
        value = bus.read(base + 4*i) & 0xff
        if value == 0:
            break
        chars.append(chr(value))
    return "".join(chars)
