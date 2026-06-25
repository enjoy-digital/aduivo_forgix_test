#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from micropython import uartbone_bridge


# Test Helpers -------------------------------------------------------------------------------------


class FakeBus:
    def __init__(self):
        self.registers = {}
        self.reads     = []
        self.writes    = []

    def read(self, address):
        self.reads.append(address)
        return self.registers.get(address, address ^ 0x5a5a0000)

    def write(self, address, value):
        value &= 0xffffffff
        self.registers[address] = value
        self.writes.append((address, value))


def payload(values):
    data = bytearray()
    for value in values:
        data += (value & 0xffffffff).to_bytes(4, byteorder="big")
    return bytes(data)


def frame(command, length, word_address, values=()):
    data = bytearray((command, length))
    data += word_address.to_bytes(4, byteorder="big")
    data += payload(values)
    return bytes(data)


class FakeStream:
    def __init__(self, data=b""):
        self.data = bytearray(data)
        self.writes = bytearray()

    @property
    def buffer(self):
        return self

    def read(self, count):
        if not self.data:
            return b""
        data = self.data[:count]
        del self.data[:count]
        return bytes(data)

    def write(self, data):
        self.writes.extend(data)

    def flush(self):
        pass


# Tests --------------------------------------------------------------------------------------------


class UARTBoneBridgeTest(unittest.TestCase):
    def test_incrementing_write_burst(self):
        bus = FakeBus()
        bridge = uartbone_bridge.UARTBoneBridge(bus)

        response = bridge.feed(frame(
            uartbone_bridge.CMD_WRITE_BURST_INCR,
            3,
            0x1000 // 4,
            (0x11223344, 0x55667788, 0x99aabbcc),
        ))

        self.assertEqual(response, b"")
        self.assertEqual(bus.writes, [
            (0x1000, 0x11223344),
            (0x1004, 0x55667788),
            (0x1008, 0x99aabbcc),
        ])

    def test_fixed_write_burst(self):
        bus = FakeBus()
        bridge = uartbone_bridge.UARTBoneBridge(bus)

        bridge.feed(frame(
            uartbone_bridge.CMD_WRITE_BURST_FIXED,
            2,
            0x2000 // 4,
            (0x00000011, 0x00000022),
        ))

        self.assertEqual(bus.writes, [
            (0x2000, 0x00000011),
            (0x2000, 0x00000022),
        ])

    def test_incrementing_read_burst(self):
        bus = FakeBus()
        bus.registers[0x3000] = 0x11223344
        bus.registers[0x3004] = 0x55667788
        bus.registers[0x3008] = 0x99aabbcc
        bridge = uartbone_bridge.UARTBoneBridge(bus)

        response = bridge.feed(frame(
            uartbone_bridge.CMD_READ_BURST_INCR,
            3,
            0x3000 // 4,
        ))

        self.assertEqual(response, payload((0x11223344, 0x55667788, 0x99aabbcc)))
        self.assertEqual(bus.reads, [0x3000, 0x3004, 0x3008])

    def test_fixed_read_burst(self):
        bus = FakeBus()
        bus.registers[0x4000] = 0x12345678
        bridge = uartbone_bridge.UARTBoneBridge(bus)

        response = bridge.feed(frame(
            uartbone_bridge.CMD_READ_BURST_FIXED,
            3,
            0x4000 // 4,
        ))

        self.assertEqual(response, payload((0x12345678, 0x12345678, 0x12345678)))
        self.assertEqual(bus.reads, [0x4000, 0x4000, 0x4000])

    def test_partial_frame_is_buffered(self):
        bus = FakeBus()
        bus.registers[0x5000] = 0xa5a55a5a
        bridge = uartbone_bridge.UARTBoneBridge(bus)
        request = frame(uartbone_bridge.CMD_READ_BURST_INCR, 1, 0x5000 // 4)

        self.assertEqual(bridge.feed(request[:3]), b"")
        self.assertEqual(bridge.feed(request[3:]), payload((0xa5a55a5a,)))

    def test_invalid_command_is_dropped(self):
        bus = FakeBus()
        bus.registers[0x6000] = 0x0badcafe
        bridge = uartbone_bridge.UARTBoneBridge(bus)

        response = bridge.feed(
            b"\xff\x7e" +
            frame(uartbone_bridge.CMD_READ_BURST_INCR, 1, 0x6000 // 4)
        )

        self.assertEqual(response, payload((0x0badcafe,)))
        self.assertEqual(bus.reads, [0x6000])

    def test_zero_length_command_is_ignored(self):
        bus = FakeBus()
        bridge = uartbone_bridge.UARTBoneBridge(bus)

        response = bridge.feed(bytes((uartbone_bridge.CMD_READ_BURST_INCR, 0)))

        self.assertEqual(response, b"")
        self.assertEqual(bus.reads, [])

    def test_idle_escape_sequence_exits_run_loop(self):
        bus = FakeBus()
        bridge = uartbone_bridge.UARTBoneBridge(bus)
        stream = FakeStream(uartbone_bridge.DEFAULT_ESCAPE_BYTE * uartbone_bridge.DEFAULT_ESCAPE_COUNT)

        bridge.run(input_stream=stream, output_stream=stream)

        self.assertEqual(bus.reads, [])
        self.assertEqual(bus.writes, [])


if __name__ == "__main__":
    unittest.main()
