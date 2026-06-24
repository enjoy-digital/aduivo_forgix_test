# Adiuvo Forgix LiteX Test

This repository documents one practical test flow for the LiteX-Boards
`adiuvo_forgix` target: build the RP2350 SPIBone design, load the FPGA from
MicroPython, then exercise LiteX CSRs over SPIBone.

It follows the same general approach as
https://github.com/enjoy-digital/litex_rp2040_pmod_test: use a small SPIBone
bridge so an RP-family microcontroller can access LiteX CSRs without putting a
soft CPU in the FPGA.

> NOTE: This flow was validated on real Forgix hardware on 2026-06-24 with
> MicroPython v1.28.0 on the RP2350 and Efinity 2025.1 generating the passive
> x1 FPGA image.

## Test Flow

The flow is intentionally single-path:

- build the `adiuvo_forgix` LiteX target with `--with-spibone`,
- expose the generated Efinity passive x1 image to the RP2350 with
  `mpremote mount`,
- load that bitstream from MicroPython without storing it in RP2350 flash,
- reuse the same RP2350 pins for 3-wire SPIBone,
- read the LiteX identifier, test the scratch CSR, and drive the RGB LEDs.

The current LiteX design is CPU-less. The `--with-spibone` build adds a
Wishbone master on the RP2350 passive-SPI pins:

| Signal | RP2350 GPIO | FPGA pin |
| --- | ---: | --- |
| CS_N | 1 | G3 |
| SCK | 2 | F3 |
| MOSI / bidirectional data | 3 | F2 |

The MicroPython FPGA loader also uses the board configuration pins:

| Signal | RP2350 GPIO |
| --- | ---: |
| FPGA RESET / CRESET_N | 4 |
| FPGA DONE | 5 |
| FPGA STATUS | 6 |
| FPGA OSC_EN | 19 |

The documented loader path only drives `CS_N`, `SCK`, and `MOSI`; it does not
claim an RP2350 MISO pin.

## References

- Forgix public files:
  https://bitbucket.org/adiuvo-engineering/forgix_public/src/main/
- Forgix schematic PDF:
  https://bitbucket.org/adiuvo-engineering/forgix_public/src/main/Schematic/RP2350_FPGA_eensy.pdf
- Forgix KiCad archive:
  https://bitbucket.org/adiuvo-engineering/forgix_public/src/main/Kicad_Project/RP2350_FPGA_eensy-main.zip
- RP2040 PMOD SPIBone reference:
  https://github.com/enjoy-digital/litex_rp2040_pmod_test

## Requirements

- LiteX and LiteX-Boards with the `adiuvo_forgix` target installed.
- Efinix Efinity in `PATH`.
- MicroPython running on the Forgix RP2350.
- `mpremote` on the host.

Install `mpremote`:

```sh
python3 -m pip install -r requirements.txt
```

## Board Firmware

The Forgix RP2350 must be running MicroPython before using this test flow.
`mpremote` talks to the MicroPython REPL and filesystem; a factory Pico SDK CDC
firmware or UF2 bootloader device is not enough.

If needed, put the RP2350 in UF2 bootloader mode and copy the Raspberry Pi Pico
2 MicroPython UF2 from https://micropython.org/download/RPI_PICO2/ onto the
mounted `RP2350` drive.

Verify the board firmware before loading the FPGA:

```sh
mpremote connect /dev/ttyACM0 exec \
    "import sys; print(sys.platform); print(sys.implementation.name)"
```

Expected output:

```text
rp2
micropython
```

## Build

Build the SPIBone test design:

```sh
python3 -m litex_boards.targets.adiuvo_forgix \
    --build \
    --with-spibone \
    --output-dir build/adiuvo_forgix
```

The generated passive-SPI image is:

```text
build/adiuvo_forgix/gateware/outflow/adiuvo_forgix.hex
```

Regenerate the MicroPython CSR map from the LiteX build:

```sh
python3 tools/csr2py.py build/adiuvo_forgix/csr.csv --output micropython/csr.py
```

For a quick LiteX integration check without running Efinity place-and-route:

```sh
python3 -m litex_boards.targets.adiuvo_forgix \
    --build \
    --with-spibone \
    --output-dir build/adiuvo_forgix \
    --no-compile
```

## Host Checks

The parser tests do not require hardware:

```sh
python3 -m unittest discover -s tests
```

## Load And Test

Copy the MicroPython test modules to the RP2350:

```sh
mpremote connect /dev/ttyACM0 fs cp micropython/fpga_loader.py :fpga_loader.py
mpremote connect /dev/ttyACM0 fs cp micropython/spibone3.py :spibone3.py
mpremote connect /dev/ttyACM0 fs cp micropython/csr.py :csr.py
mpremote connect /dev/ttyACM0 fs cp micropython/test_forgix.py :test_forgix.py
mpremote connect /dev/ttyACM0 fs cp micropython/load_and_test.py :load_and_test.py
```

Run the complete test while mounting the host bitstream directory:

```sh
mpremote connect /dev/ttyACM0 mount build/adiuvo_forgix/gateware/outflow exec \
    "import sys; sys.path.append('/'); import load_and_test; load_and_test.main()"
```

The bitstream is read from `/remote/adiuvo_forgix.hex` through `mpremote mount`;
it is not copied to RP2350 flash. The `sys.path` addition keeps the modules
copied to the RP2350 root filesystem importable while `/remote` is mounted.

Expected transcript shape:

```text
Forgix LiteX load-and-test
Loading FPGA:
  wrote 65536 bytes
  wrote 131072 bytes
  ...
  DONE=1 STATUS=1
Programmed <bitstream-size> bytes
Forgix LiteX SPIBone test
Identifier:
  LiteX SoC on Adiuvo Forgix ...
Scratch CSR:
  original: 0x........
  write/read: 0x12345678 / 0x12345678
  write/read: 0xa5a55a5a / 0xa5a55a5a
  write/read: 0x........ / 0x........
LED CSR:
  leds_out = 0x0
  leds_out = 0x1
  leds_out = 0x2
  leds_out = 0x4
  leds_out = 0x7
  leds_out = 0x0
  leds_out = 0x7
  leds_out = 0x0
Done
```

## Loader Notes

The MicroPython loader uses passive SPI width 1, SPI mode 3, `OSC_EN` before
programming, `SS_N` low before releasing `CRESET_N`, `SS_N` held low through
the transfer, and 32 extra zero bytes after the bitstream.

The run aborts if `DONE` does not go high or if `STATUS` is low after
configuration.

The documented flow uses the generated Efinity `.hex` file directly.
