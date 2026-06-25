#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import sys

try:
    from spibone3 import SPIBone3Wire
except ImportError:
    try:
        from micropython.spibone3 import SPIBone3Wire
    except ImportError:
        SPIBone3Wire = None

# LiteX UARTBone Commands --------------------------------------------------------------------------


CMD_WRITE_BURST_INCR  = 0x01
CMD_READ_BURST_INCR   = 0x02
CMD_WRITE_BURST_FIXED = 0x03
CMD_READ_BURST_FIXED  = 0x04

READ_COMMANDS = (
    CMD_READ_BURST_INCR,
    CMD_READ_BURST_FIXED,
)

WRITE_COMMANDS = (
    CMD_WRITE_BURST_INCR,
    CMD_WRITE_BURST_FIXED,
)

COMMANDS = READ_COMMANDS + WRITE_COMMANDS

DEFAULT_ADDR_BYTES = 4
DEFAULT_ESCAPE_BYTE = b"\x1d"
DEFAULT_ESCAPE_COUNT = 3

# Helpers ------------------------------------------------------------------------------------------


def _to_bytes(data):
    if data is None:
        return b""
    if isinstance(data, int):
        return bytes((data & 0xff,))
    if isinstance(data, str):
        return data.encode("latin1")
    return bytes(data)


def _read_uint(data, offset, length):
    value = 0
    for i in range(length):
        value = (value << 8) | data[offset + i]
    return value


def _append_u32(data, value):
    value &= 0xffffffff
    for shift in (24, 16, 8, 0):
        data.append((value >> shift) & 0xff)


def _binary_stream(stream):
    return getattr(stream, "buffer", stream)


def _read_stream_byte(stream):
    data = stream.read(1)
    if data is None:
        return b""
    if isinstance(data, int):
        return bytes((data & 0xff,))
    if isinstance(data, str):
        if not data:
            return b""
        return bytes((ord(data[0]) & 0xff,))
    return bytes(data)


def _write_stream(stream, data):
    try:
        stream.write(data)
    except TypeError:
        stream.write("".join(chr(byte) for byte in data))
    flush = getattr(stream, "flush", None)
    if flush is not None:
        flush()


def _make_poller(stream):
    try:
        try:
            import uselect as select
        except ImportError:
            import select
        poller = select.poll()
        poller.register(stream, select.POLLIN)
        return poller
    except Exception:
        return None

# UARTBone Bridge ----------------------------------------------------------------------------------


class UARTBoneBridge:
    def __init__(self, bus, addr_bytes=DEFAULT_ADDR_BYTES):
        if addr_bytes <= 0:
            raise ValueError("addr_bytes must be greater than zero")
        self.bus        = bus
        self.addr_bytes = addr_bytes
        self.rx         = bytearray()

    def reset(self):
        self.rx = bytearray()

    def pending(self):
        return len(self.rx) != 0

    def drop(self, count):
        self.rx = self.rx[count:]

    def feed(self, data):
        self.rx.extend(_to_bytes(data))
        response = bytearray()

        while len(self.rx) >= 2:
            command = self.rx[0]
            if command not in COMMANDS:
                self.drop(1)
                continue

            length = self.rx[1]
            if length == 0:
                self.drop(2)
                continue

            header_length = 2 + self.addr_bytes
            if len(self.rx) < header_length:
                break

            payload_length = 4*length if command in WRITE_COMMANDS else 0
            frame_length   = header_length + payload_length
            if len(self.rx) < frame_length:
                break

            word_address = _read_uint(self.rx, 2, self.addr_bytes)
            payload      = self.rx[header_length:frame_length]
            response.extend(self.handle(command, length, word_address, payload))
            self.drop(frame_length)

        return bytes(response)

    def handle(self, command, length, word_address, payload=b""):
        byte_address = word_address * 4
        fixed        = command in (CMD_WRITE_BURST_FIXED, CMD_READ_BURST_FIXED)
        response     = bytearray()

        if command in READ_COMMANDS:
            for i in range(length):
                address = byte_address if fixed else byte_address + 4*i
                _append_u32(response, self.bus.read(address))
            return response

        if command in WRITE_COMMANDS:
            for i in range(length):
                address = byte_address if fixed else byte_address + 4*i
                value   = _read_uint(payload, 4*i, 4)
                self.bus.write(address, value)
            return response

        return response

    def run(self, input_stream=None, output_stream=None, timeout_ms=250,
        escape_byte=DEFAULT_ESCAPE_BYTE, escape_count=DEFAULT_ESCAPE_COUNT):
        if input_stream is None:
            input_stream = sys.stdin
        if output_stream is None:
            output_stream = sys.stdout

        poller = _make_poller(input_stream)
        reader = _binary_stream(input_stream)
        writer = _binary_stream(output_stream)
        escape_seen = 0

        while True:
            if poller is not None:
                events = poller.poll(timeout_ms)
                if not events:
                    if self.pending():
                        self.reset()
                    continue

            data = _read_stream_byte(reader)
            if not data:
                continue

            if escape_byte is not None and not self.pending() and data == escape_byte:
                escape_seen += 1
                if escape_seen >= escape_count:
                    return
                continue
            escape_seen = 0

            response = self.feed(data)
            if response:
                _write_stream(writer, response)

# Run ----------------------------------------------------------------------------------------------


def main(bus=None, addr_bytes=DEFAULT_ADDR_BYTES, half_period_us=1, timeout_bytes=256, timeout_ms=250):
    micropython_module = None
    try:
        import micropython
        micropython_module = micropython
        micropython_module.kbd_intr(-1)
    except ImportError:
        pass

    if bus is None:
        if SPIBone3Wire is None:
            raise RuntimeError("SPIBone3Wire is unavailable; pass an explicit bus")
        bus = SPIBone3Wire(half_period_us=half_period_us, timeout_bytes=timeout_bytes)

    try:
        UARTBoneBridge(bus, addr_bytes=addr_bytes).run(timeout_ms=timeout_ms)
    finally:
        if micropython_module is not None:
            micropython_module.kbd_intr(3)


if __name__ == "__main__":
    main()
