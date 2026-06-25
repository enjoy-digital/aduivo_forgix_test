#!/usr/bin/env python3
#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import argparse
from pathlib import Path


# Conversion ---------------------------------------------------------------------------------------


def convert(input_path, output_path):
    input_path  = Path(input_path)
    output_path = Path(output_path)
    written     = 0

    with output_path.open("wb") as f:
        for chunk in iter_bitstream_chunks(input_path):
            f.write(chunk)
            written += len(chunk)

    return written


def iter_bitstream_chunks(path, chunk_size=4096):
    if detect_bitstream_format(path) == "ihex":
        byte_iter = _iter_intel_hex_bytes(path)
    else:
        byte_iter = _iter_plain_hex_bytes(path)

    chunk = bytearray()
    for byte in byte_iter:
        chunk.append(byte)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = bytearray()
    if chunk:
        yield chunk


def detect_bitstream_format(path):
    with open(path, "rb") as f:
        while True:
            data = f.read(256)
            if not data:
                return "hex"
            for byte in data:
                if byte not in (9, 10, 13, 32):
                    return "ihex" if byte == ord(":") else "hex"


def _iter_plain_hex_bytes(path):
    high = -1
    with open(path, "rb") as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            for byte in data:
                if byte in (9, 10, 13, 32):
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


# CLI ----------------------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Convert Efinity HEX bitstreams to raw binary.")
    parser.add_argument("input", type=Path, help="Input plain or Intel HEX bitstream.")
    parser.add_argument("--output", "-o", type=Path, help="Output binary bitstream.")
    args = parser.parse_args()

    output = args.output if args.output is not None else args.input.with_suffix(".bin")
    written = convert(args.input, output)
    print("Wrote %u bytes to %s" % (written, output))


if __name__ == "__main__":
    main()
