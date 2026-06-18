#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import sys
import time

from machine import Pin, SPI

# Constants ----------------------------------------------------------------------------------------


DEFAULT_PINS = {
    "cs_n"    : 1,
    "sck"     : 2,
    "mosi"    : 3,
    "reset_n" : 4,
    "done"    : 5,
    "status"  : 6,
    "osc_en"  : 19,
}

DEFAULT_BITSTREAM = "/remote/adiuvo_forgix.hex"

# FPGA Loader --------------------------------------------------------------------------------------


class ForgixFPGALoader:
    def __init__(
        self,
        pins=None,
        spi_id=0,
        baudrate=8000000,
        chunk_size=1024,
        done_timeout_ms=500,
        extra_clock_bytes=32,
    ):
        if pins is None:
            pins = DEFAULT_PINS
        self.pins              = pins
        self.spi_id            = spi_id
        self.baudrate          = baudrate
        self.chunk_size        = chunk_size
        self.done_timeout_ms   = done_timeout_ms
        self.extra_clock_bytes = extra_clock_bytes
        self.spi               = None

    def _configure_pins(self):
        self.osc_en  = Pin(self.pins["osc_en"],  Pin.OUT, value=1)
        time.sleep_ms(1)
        self.cs_n    = Pin(self.pins["cs_n"],    Pin.OUT, value=1)
        self.reset_n = Pin(self.pins["reset_n"], Pin.OUT, value=1)
        self.done    = Pin(self.pins["done"],    Pin.IN)
        self.status  = Pin(self.pins["status"],  Pin.IN)

    def _configure_spi(self):
        kwargs = {
            "baudrate" : self.baudrate,
            "polarity" : 1,
            "phase"    : 1,
            "bits"     : 8,
            "firstbit" : SPI.MSB,
            "sck"      : Pin(self.pins["sck"]),
            "mosi"     : Pin(self.pins["mosi"]),
        }
        try:
            self.spi = SPI(self.spi_id, **kwargs)
        except TypeError:
            if "miso" not in self.pins or self.pins["miso"] is None:
                raise TypeError("MicroPython SPI requires an explicit MISO pin.")
            kwargs["miso"] = Pin(self.pins["miso"])
            self.spi = SPI(self.spi_id, **kwargs)

    def begin(self):
        self._configure_pins()
        self._configure_spi()
        self.cs_n.value(0)
        self.reset_n.value(0)
        time.sleep_ms(2)
        self.reset_n.value(1)
        time.sleep_ms(5)

    def finish(self):
        if self.extra_clock_bytes:
            self.spi.write(bytes(self.extra_clock_bytes))

        deadline = time.ticks_add(time.ticks_ms(), self.done_timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if self.done.value():
                self.cs_n.value(1)
                return {
                    "done"   : self.done.value(),
                    "status" : self.status.value(),
                }
            time.sleep_ms(1)

        self.cs_n.value(1)
        raise OSError("FPGA DONE did not go high")

    def abort(self):
        try:
            self.cs_n.value(1)
            self.reset_n.value(0)
            time.sleep_ms(2)
            self.reset_n.value(1)
        except AttributeError:
            pass

    def close(self):
        if self.spi is not None:
            try:
                self.spi.deinit()
            except AttributeError:
                pass
            self.spi = None

    def program(self, path, progress=True):
        written = 0
        next_report = 64 * 1024
        self.begin()
        try:
            for chunk in iter_bitstream_chunks(path, self.chunk_size):
                self.spi.write(chunk)
                written += len(chunk)
                if progress and written >= next_report:
                    print("  wrote %u bytes" % written)
                    next_report += 64 * 1024
            state = self.finish()
            if progress:
                print("  DONE=%u STATUS=%u" % (state["done"], state["status"]))
            if not state["status"]:
                raise OSError("FPGA STATUS is low after configuration")
            return written
        except Exception:
            self.abort()
            raise
        finally:
            self.close()

# Bitstream Helpers --------------------------------------------------------------------------------


def iter_bitstream_chunks(path, chunk_size=1024):
    fmt = detect_bitstream_format(path)
    if fmt == "ihex":
        for chunk in _iter_chunked(_iter_intel_hex_bytes(path), chunk_size):
            yield chunk
    elif fmt == "hex":
        for chunk in _iter_chunked(_iter_plain_hex_bytes(path), chunk_size):
            yield chunk
    else:
        raise ValueError("unsupported bitstream format")


def detect_bitstream_format(path):
    first = _first_nonspace(path)
    if first == ord(":"):
        return "ihex"
    return "hex"


def _first_nonspace(path):
    with open(path, "rb") as f:
        while True:
            data = f.read(256)
            if not data:
                return -1
            for byte in data:
                if not _is_space(byte):
                    return byte


def _iter_plain_hex_bytes(path):
    high = -1
    with open(path, "rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            for byte in data:
                if _is_space(byte):
                    continue
                value = _hex_value(byte)
                if high < 0:
                    high = value
                else:
                    yield (high << 4) | value
                    high = -1
        if high >= 0:
            raise ValueError("hex file has an odd number of hex digits")


def _iter_intel_hex_bytes(path):
    upper = 0
    next_address = None
    with open(path, "rb") as f:
        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line[0] != ord(":"):
                raise ValueError("mixed Intel HEX and non-Intel HEX content")

            record = _decode_hex_bytes(line[1:])
            if len(record) < 5:
                raise ValueError("short Intel HEX record")

            byte_count  = record[0]
            address     = (record[1] << 8) | record[2]
            record_type = record[3]
            if len(record) != byte_count + 5:
                raise ValueError("bad Intel HEX record length")
            data     = record[4 : 4 + byte_count]
            checksum = record[4 + byte_count]

            if (sum(record[: 4 + byte_count]) + checksum) & 0xff:
                raise ValueError("bad Intel HEX checksum")

            if record_type == 0x00:
                absolute = upper + address
                if next_address is None:
                    next_address = absolute
                if absolute < next_address:
                    raise ValueError("Intel HEX records are not monotonic")
                while next_address < absolute:
                    yield 0xff
                    next_address += 1
                for byte in data:
                    yield byte
                    next_address += 1
            elif record_type == 0x01:
                break
            elif record_type == 0x02:
                if byte_count != 2:
                    raise ValueError("bad Intel HEX segment-address record")
                upper = ((data[0] << 8) | data[1]) << 4
            elif record_type == 0x04:
                if byte_count != 2:
                    raise ValueError("bad Intel HEX linear-address record")
                upper = ((data[0] << 8) | data[1]) << 16


def _iter_chunked(byte_iter, chunk_size):
    chunk = bytearray()
    for byte in byte_iter:
        chunk.append(byte)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = bytearray()
    if chunk:
        yield chunk


def _decode_hex_bytes(data):
    if len(data) & 1:
        raise ValueError("hex record has an odd number of digits")
    decoded = bytearray(len(data) // 2)
    out = 0
    for i in range(0, len(data), 2):
        decoded[out] = (_hex_value(data[i]) << 4) | _hex_value(data[i + 1])
        out += 1
    return decoded


def _hex_value(byte):
    if 48 <= byte <= 57:
        return byte - 48
    if 65 <= byte <= 70:
        return byte - 55
    if 97 <= byte <= 102:
        return byte - 87
    raise ValueError("invalid hex character")


def _is_space(byte):
    return byte in (9, 10, 13, 32)

# Run ----------------------------------------------------------------------------------------------


def main(path=None):
    if path is None:
        path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BITSTREAM
    print("Programming FPGA from %s" % path)
    loader = ForgixFPGALoader()
    written = loader.program(path)
    print("Programmed %u bytes" % written)


if __name__ == "__main__":
    main()
