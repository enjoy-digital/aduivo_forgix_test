# Adiuvo Forgix LiteX Test

This repository documents a practical test flow for the LiteX-Boards
`adiuvo_forgix` target.

It is based on the same idea as
https://github.com/enjoy-digital/litex_rp2040_pmod_test: use a small SPIBone
bridge so an RP-family microcontroller can access LiteX CSRs without putting a
soft CPU in the FPGA.

## What This Tests

- Build the LiteX-Boards `adiuvo_forgix` target.
- Load the generated passive x1 Efinity image through the Forgix RP2350 loader.
- Smoke-test the default UARTBone path.
- Smoke-test the optional `--with-spibone` RP2350 path from MicroPython.

The current LiteX target is CPU-less. The default build exposes UARTBone on the
FPGA header pins. The optional `--with-spibone` build adds a 3-wire SPIBone
Wishbone master on the RP2350 passive-SPI pins:

| Signal | RP2350 GPIO | FPGA pin |
| --- | ---: | --- |
| CS_N | 1 | G3 |
| SCK | 2 | F3 |
| MOSI / bidirectional data | 3 | F2 |

The MicroPython examples assume the FPGA has already been configured with a
LiteX bitstream built with `--with-spibone`.

## References

- Forgix public files:
  https://bitbucket.org/adiuvo-engineering/forgix_public/src/main/
- Forgix schematic PDF:
  https://bitbucket.org/adiuvo-engineering/forgix_public/src/main/Schematic/RP2350_FPGA_eensy.pdf
- Forgix KiCad archive:
  https://bitbucket.org/adiuvo-engineering/forgix_public/src/main/Kicad_Project/RP2350_FPGA_eensy-main.zip
- Forgix RP2350 loader:
  https://bitbucket.org/adiuvo-engineering/forgix_public/src/main/BitStream_Loader/
- RP2040 PMOD SPIBone reference:
  https://github.com/enjoy-digital/litex_rp2040_pmod_test

## Requirements

- LiteX and LiteX-Boards with the `adiuvo_forgix` target installed.
- Efinix Efinity in `PATH`.
- The Forgix loader firmware already running on the RP2350 for the load step.
- `mpremote` for the MicroPython test step.

Install the host-side Python helper:

```sh
python3 -m pip install -r requirements.txt
```

## Build

Build the default UARTBone design:

```sh
python3 -m litex_boards.targets.adiuvo_forgix \
    --build \
    --output-dir build/adiuvo_forgix
```

Build the RP2350 SPIBone variant and regenerate the MicroPython CSR map:

```sh
./scripts/build_litex.sh
```

The Efinity passive-SPI image is generated at:

```text
build/adiuvo_forgix/gateware/outflow/adiuvo_forgix.hex
```

Use `--no-compile` while iterating on the LiteX Python integration:

```sh
./scripts/build_litex.sh --no-compile
```

## Load

Build or install the Forgix loader from the public Forgix repository, then point
this repo at its host Python package:

```sh
export FORGE_LOADER_HOST=/path/to/forgix_public/BitStream_Loader/host
export FORGIX_PORT=/dev/ttyACM0
./scripts/load_forgix.sh
```

Override the bitstream path or SPI rate when needed:

```sh
FORGIX_SPI_HZ=8000000 ./scripts/load_forgix.sh \
    build/adiuvo_forgix/gateware/outflow/adiuvo_forgix.hex
```

On Windows, run the equivalent command from the Forgix loader `host/`
directory:

```powershell
python -m forge_loader.cli --port COM7 --file path\to\adiuvo_forgix.hex --spi-hz 8000000
```

## UARTBone Smoke Test

The default LiteX target keeps UARTBone enabled on the FPGA header `serial`
resource. Connect a USB-UART adapter to the board header pins used by the
LiteX `serial` resource, then run:

```sh
litex_server --uart --uart-port /dev/ttyUSB0 --csr-csv build/adiuvo_forgix/csr.csv
```

In another shell:

```sh
litex_cli --ident
litex_cli --regs
```

This validates the base LiteX target without relying on RP2350-side firmware.

## MicroPython SPIBone Test

This test requires the FPGA to be configured with the `--with-spibone` build.
The RP2350 must be running MicroPython firmware, not the Forge loader firmware.

Copy the helper modules to the RP2350:

```sh
mpremote connect /dev/ttyACM0 fs cp micropython/spibone3.py :spibone3.py
mpremote connect /dev/ttyACM0 fs cp micropython/csr.py :csr.py
```

Run the test directly from the host:

```sh
mpremote connect /dev/ttyACM0 run micropython/test_forgix.py
```

Expected output:

- the LiteX identifier string,
- a scratch CSR write/readback,
- a short RGB LED pattern through the `leds_out` CSR.

If the CSR map changes, regenerate `micropython/csr.py` from the LiteX build:

```sh
python3 tools/csr2py.py build/adiuvo_forgix/csr.csv --output micropython/csr.py
mpremote connect /dev/ttyACM0 fs cp micropython/csr.py :csr.py
```

## Firmware Caveat

The Forgix loader firmware and the MicroPython firmware are separate RP2350
images. The current flow is therefore:

1. run the Forge loader firmware to configure the FPGA, or configure the FPGA by
   another method,
2. run MicroPython on the RP2350 to exercise SPIBone.

A single-cable production test should merge these two roles in RP2350 firmware:
load the FPGA bitstream first, then expose a USB-to-SPIBone bridge. The
`litex_rp2040_pmod_test` `usb2spibone` firmware is the closest starting point
for that approach.
