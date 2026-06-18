#!/usr/bin/env python3

#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import re
import csv
import argparse
from pathlib import Path

# Helpers ------------------------------------------------------------------------------------------


def const_name(prefix, name):
    name = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").upper()
    if name and name[0].isdigit():
        name = "_" + name
    return f"{prefix}_{name}"


def parse_value(value):
    value = value.strip()
    if value.startswith("0x"):
        return int(value, 16)
    try:
        return int(value, 10)
    except ValueError:
        return value


def py_value(value):
    if isinstance(value, int):
        return f"0x{value:08x}"
    return repr(value)

# Conversion ---------------------------------------------------------------------------------------


def convert(path):
    constants = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.reader(line for line in f if not line.startswith("#")):
            if len(row) < 3:
                continue
            kind  = row[0]
            name  = row[1]
            value = parse_value(row[2])

            if kind == "csr_base":
                constants.append((const_name("CSR_BASE", name), value))
            elif kind == "csr_register":
                constants.append((const_name("CSR", name), value))
            elif kind == "constant":
                if name == "config_identifier":
                    continue
                constants.append((const_name("CONFIG", name.removeprefix("config_")), value))
            elif kind == "memory_region":
                constants.append((const_name("MEMORY", name), value))
    return constants


def render(constants, source):
    lines = [
        "# Auto-generated from LiteX csr.csv.",
        f"# Source: {source}",
        "",
    ]
    width = max((len(name) for name, _ in constants), default=0)
    for name, value in constants:
        lines.append(f"{name:<{width}} = {py_value(value)}")
    lines.append("")
    return "\n".join(lines)

# Run ----------------------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Convert LiteX csr.csv to MicroPython constants.")
    parser.add_argument("csr_csv",       type=Path, help="LiteX CSR CSV file.")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output Python file.")
    args = parser.parse_args()

    text = render(convert(args.csr_csv), args.csr_csv)
    if args.output is None:
        print(text, end="")
    else:
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
