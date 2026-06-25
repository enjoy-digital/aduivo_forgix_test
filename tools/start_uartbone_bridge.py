#!/usr/bin/env python3

#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import subprocess
import sys
import time


BRIDGE_EXEC = "import sys; sys.path.append('/'); import uartbone_bridge; uartbone_bridge.main()"


def start_bridge(port, mpremote="mpremote", settle=1.0, terminate_timeout=1.0):
    process = subprocess.Popen(
        [mpremote, "connect", port, "exec", BRIDGE_EXEC],
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
        text   = True,
    )

    time.sleep(settle)
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        raise RuntimeError(
            "bridge process exited early with code %s\n%s%s" % (
                process.returncode,
                stdout,
                stderr,
            )
        )

    process.terminate()
    try:
        process.wait(timeout=terminate_timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=terminate_timeout)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start the Forgix MicroPython UARTBone bridge.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="MicroPython USB serial port.")
    parser.add_argument("--mpremote", default="mpremote", help="mpremote executable.")
    parser.add_argument("--settle", default=1.0, type=float, help="Seconds to let the bridge start before detaching.")
    args = parser.parse_args(argv)

    try:
        start_bridge(port=args.port, mpremote=args.mpremote, settle=args.settle)
    except Exception as error:
        print(error, file=sys.stderr)
        return 1

    print("UARTBone bridge running on %s" % args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
