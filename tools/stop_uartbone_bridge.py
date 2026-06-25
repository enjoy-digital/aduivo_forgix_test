#!/usr/bin/env python3

#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import time

import serial


def stop_bridge(port, baudrate=1000000, escape_count=3, settle=0.2, retries=5, retry_delay=0.5):
    last_error = None
    for _ in range(retries):
        try:
            with serial.Serial(port, baudrate=baudrate, timeout=settle) as uart:
                uart.write(b"\x1d" * escape_count)
                uart.flush()
                time.sleep(settle)
                return
        except serial.SerialException as error:
            last_error = error
            time.sleep(retry_delay)
    raise last_error


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stop the Forgix MicroPython UARTBone bridge.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="MicroPython USB serial port.")
    parser.add_argument("--baudrate", default=1000000, type=int, help="UART baudrate.")
    parser.add_argument("--escape-count", default=3, type=int, help="Number of Ctrl-] bytes to send.")
    parser.add_argument("--settle", default=0.2, type=float, help="Seconds to wait after sending the escape.")
    parser.add_argument("--retries", default=5, type=int, help="Open retries for re-enumerating USB serial ports.")
    parser.add_argument("--retry-delay", default=0.5, type=float, help="Seconds between open retries.")
    args = parser.parse_args(argv)

    stop_bridge(
        port         = args.port,
        baudrate     = args.baudrate,
        escape_count = args.escape_count,
        settle       = args.settle,
        retries      = args.retries,
        retry_delay  = args.retry_delay,
    )
    print("UARTBone bridge stop sequence sent to %s" % args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
