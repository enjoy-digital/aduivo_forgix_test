# Adiuvo Forgix LiteX Test

This repository documents a practical test flow for the LiteX-Boards
`adiuvo_forgix` target.

It is based on the same idea as
https://github.com/enjoy-digital/litex_rp2040_pmod_test: use a small SPIBone
bridge so an RP-family microcontroller can access LiteX CSRs without putting a
soft CPU in the FPGA.

## What This Tests

- Build the LiteX-Boards `adiuvo_forgix` target.
- Load the generated passive x1 Efinity image directly from MicroPython, or
  through the Forgix RP2350 loader as a reference path.
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

The direct MicroPython loader uses the same RP2350 pins as the public Forge
loader firmware:

| Signal | RP2350 GPIO |
| --- | ---: |
| FPGA SS_N / CS | 1 |
| FPGA SCLK | 2 |
| FPGA MOSI | 3 |
| FPGA RESET / CRESET_N | 4 |
| FPGA DONE | 5 |
| FPGA STATUS | 6 |
| FPGA OSC_EN | 19 |

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
- MicroPython running on the RP2350 for the direct load/test path.
- `mpremote` for the MicroPython load/test step.
- Optional: the Forgix loader firmware for the reference load path.

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
python3 scripts/build_litex.py
```

The Efinity passive-SPI image is generated at:

```text
build/adiuvo_forgix/gateware/outflow/adiuvo_forgix.hex
```

Use `--no-compile` while iterating on the LiteX Python integration:

```sh
python3 scripts/build_litex.py --no-compile
```

## MicroPython Direct Load And Test

The preferred single-firmware flow is to run MicroPython on the RP2350, then
let the RP2350 configure the FPGA over passive SPI and immediately reuse the
same pins for SPIBone CSR access.

Copy the MicroPython helper modules to the RP2350:

```sh
mpremote connect /dev/ttyACM0 fs cp micropython/fpga_loader.py :fpga_loader.py
mpremote connect /dev/ttyACM0 fs cp micropython/spibone3.py :spibone3.py
mpremote connect /dev/ttyACM0 fs cp micropython/csr.py :csr.py
mpremote connect /dev/ttyACM0 fs cp micropython/test_forgix.py :test_forgix.py
mpremote connect /dev/ttyACM0 fs cp micropython/load_and_test.py :load_and_test.py
```

Then either copy the Efinity passive-SPI image to the RP2350 filesystem:

```sh
mpremote connect /dev/ttyACM0 fs cp \
    build/adiuvo_forgix/gateware/outflow/adiuvo_forgix.hex \
    :adiuvo_forgix.hex

mpremote connect /dev/ttyACM0 exec \
    "import load_and_test; load_and_test.main('adiuvo_forgix.hex')"
```

Or avoid storing the bitstream in RP2350 flash by mounting the host build
directory for the duration of the test:

```sh
mpremote connect /dev/ttyACM0 mount build/adiuvo_forgix/gateware/outflow exec \
    "import load_and_test; load_and_test.main('/remote/adiuvo_forgix.hex')"
```

The loader accepts the Efinity `.hex` file directly. A `.bin` converted from
the `.hex` also works and will load faster because MicroPython does not need to
parse text while streaming to SPI.

To only configure the FPGA, run:

```sh
mpremote connect /dev/ttyACM0 exec \
    "import fpga_loader; fpga_loader.main('adiuvo_forgix.hex')"
```

## Forge Loader Reference Path

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

This test requires the FPGA to already be configured with the `--with-spibone`
build. If you used `load_and_test.py`, this step has already run.

Copy the helper modules to the RP2350:

```sh
mpremote connect /dev/ttyACM0 fs cp micropython/spibone3.py :spibone3.py
mpremote connect /dev/ttyACM0 fs cp micropython/csr.py :csr.py
mpremote connect /dev/ttyACM0 fs cp micropython/test_forgix.py :test_forgix.py
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

## Loader Notes

The MicroPython loader mirrors the public Forge loader firmware assumptions:
SPI mode 3, passive width 1, `OSC_EN` enabled before programming, `SS_N`
asserted before `CRESET_N` is released, `SS_N` held low through the transfer,
and 32 extra zero bytes clocked after the bitstream.

The Forge loader remains useful as a known-good reference and for debugging the
raw FPGA programming path. The direct MicroPython flow is intended for a simple
one-cable validation setup: load the FPGA bitstream first, then exercise LiteX
CSRs over SPIBone without reflashing the RP2350.

The `litex_rp2040_pmod_test` `usb2spibone` firmware is still the closest
starting point for a faster native RP2350 USB-to-SPIBone bridge.
