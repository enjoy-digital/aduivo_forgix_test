# Adiuvo Forgix LiteX Test

[![](https://github.com/enjoy-digital/aduivo_forgix_test/actions/workflows/ci.yml/badge.svg)](https://github.com/enjoy-digital/aduivo_forgix_test/actions/workflows/ci.yml) ![License](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/enjoy-digital/aduivo_forgix_test)

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
- `litex_server`/`litex_client` available from the LiteX installation for the
  UARTBone-compatible host bridge.
- LiteScope from the LiteX ecosystem for the optional integrated capture demo.
- DearPyGui on the host for the optional graphical demo.

Install the Python host tools used by this repository:

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

Generate the raw binary image used by the faster loader path:

```sh
python3 tools/bitstream2bin.py \
    build/adiuvo_forgix/gateware/outflow/adiuvo_forgix.hex \
    --output build/adiuvo_forgix/gateware/outflow/adiuvo_forgix.bin
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

To build a variant where the FPGA runs the RGB LED animation itself after a
single SPIBone command, add the optional demo LED core:

```sh
python3 -m litex_boards.targets.adiuvo_forgix \
    --build \
    --with-spibone \
    --with-demo-leds \
    --output-dir build/adiuvo_forgix_demo
```

Then regenerate `micropython/csr.py` from `build/adiuvo_forgix_demo/csr.csv`.

For the richer GUI demo with PWM controls, edge-connector outputs, and
LiteScope capture probes, build the demo variant with the extra options:

```sh
python3 -m litex_boards.targets.adiuvo_forgix \
    --build \
    --with-spibone \
    --with-demo-leds \
    --with-demo-io \
    --with-demo-scope \
    --demo-scope-depth 512 \
    --output-dir build/adiuvo_forgix_demo
```

This generates both the normal SoC CSR map and the LiteScope analyzer map:

```text
build/adiuvo_forgix_demo/csr.csv
build/adiuvo_forgix_demo/analyzer.csv
```

It also keeps the integrated analyzer small enough for the T8F49 by capturing
the visible LED/demo signals and the low SPIBone bus lanes with a 512-sample
depth.

For the fast MicroPython loader path, generate the binary bitstream and the CSR
map that matches this rich demo build:

```sh
python3 tools/bitstream2bin.py \
    build/adiuvo_forgix_demo/gateware/outflow/adiuvo_forgix.hex \
    --output build/adiuvo_forgix_demo/gateware/outflow/adiuvo_forgix.bin

python3 tools/csr2py.py build/adiuvo_forgix_demo/csr.csv --output micropython/csr.py
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
mpremote connect /dev/ttyACM0 fs cp micropython/demo_forgix.py :demo_forgix.py
mpremote connect /dev/ttyACM0 fs cp micropython/load_and_test.py :load_and_test.py
```

Run the complete test while mounting the host bitstream directory:

```sh
mpremote connect /dev/ttyACM0 mount build/adiuvo_forgix/gateware/outflow exec \
    "import sys; sys.path.append('/'); import load_and_test; load_and_test.main()"
```

For the rich GUI demo bitstream, use the matching output directory instead:

```sh
mpremote connect /dev/ttyACM0 mount build/adiuvo_forgix_demo/gateware/outflow exec \
    "import sys; sys.path.append('/'); import load_and_test; load_and_test.main()"
```

The bitstream is read through `mpremote mount`; it is not copied to RP2350
flash. When `/remote/adiuvo_forgix.bin` is present, the loader uses it instead
of parsing the text `.hex` file on the RP2350. If the `.bin` file is absent, it
falls back to `/remote/adiuvo_forgix.hex`. The `sys.path` addition keeps the
modules copied to the RP2350 root filesystem importable while `/remote` is
mounted.

Expected transcript shape:

```text
Forgix LiteX load-and-test
Loading FPGA from /remote/adiuvo_forgix.bin:
  wrote 65536 bytes
  wrote 131072 bytes
  ...
  DONE=1 STATUS=1
Programmed <bitstream-size> bytes in <elapsed-ms> ms
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

With the rich demo bitstream, the LED lines are printed as `demo_leds_rgb`
instead of `leds_out`.

## Fancy Demos

After the FPGA has been loaded, the board-only demo runner can reuse the same
SPIBone CSR path for more visible RGB LED activity:

```sh
mpremote connect /dev/ttyACM0 exec \
    "import demo_forgix; demo_forgix.main('show')"
```

Available modes:

- `quick`: identifier read, scratch CSR round-trip, short RGB blink.
- `show`: color chase, binary count, and a simple software PWM fade.
- `stress`: repeated scratch CSR checks while the RGB LED remains active.

The second argument sets the number of cycles:

```sh
mpremote connect /dev/ttyACM0 exec \
    "import demo_forgix; demo_forgix.main('show', 3)"
```

Expected transcript shape:

```text
Forgix LED show
Software LED demo:
  color chase
  binary count
  white fade
Done
```

The default CPU-less gateware exposes `CSR_LEDS_OUT`, so the demo effects are
driven directly from MicroPython and finish with the LEDs off. When the
`--with-demo-leds` LiteX variant exposes `CSR_DEMO_LEDS_MODE`,
`CSR_DEMO_LEDS_RGB`, and `CSR_DEMO_LEDS_SPEED`, the `show` mode automatically
uses that hardware demo core instead.

## UARTBone-Compatible Host Bridge

For host-side tools, the RP2350 can run a MicroPython bridge that speaks the
same binary UARTBone framing used by LiteX `CommUART`. This lets the regular
LiteX server own the USB serial link and exposes the FPGA CSRs through the
standard LiteX TCP/Etherbone path.

Copy the bridge modules to the board:

```sh
mpremote connect /dev/ttyACM0 fs cp micropython/spibone3.py :spibone3.py
mpremote connect /dev/ttyACM0 fs cp micropython/uartbone_bridge.py :uartbone_bridge.py
```

Load the FPGA first, then start the bridge without resetting the RP2350:

```sh
python3 tools/start_uartbone_bridge.py --port /dev/ttyACM0
```

This helper starts `uartbone_bridge.main()` with `mpremote exec`, waits for the
bridge loop to run on the RP2350, then closes only the host-side `mpremote`
process so `litex_server` can own the same serial port.

The bridge is intentionally silent once running. Start the LiteX server in a
separate terminal:

```sh
litex_server \
    --uart \
    --uart-port=/dev/ttyACM0 \
    --uart-baudrate=1000000 \
    --addr-width=32
```

With the server running, standard LiteX clients can be reused:

```sh
litex_cli --host=localhost --port=1234 --csr-csv=build/adiuvo_forgix/csr.csv --ident --regs
```

For the demo LED gateware variant, point clients at
`build/adiuvo_forgix_demo/csr.csv` instead.

If the identifier output contains garbled text, `MicroPython`, `>>>`, or
ASCII-looking register values such as `0x6963726f`, the LiteX server is talking
to the MicroPython REPL instead of the bridge. Stop `litex_server`, reload the
FPGA if needed, rerun `tools/start_uartbone_bridge.py`, and start a fresh
`litex_server`.

The bridge disables MicroPython Ctrl-C handling while it owns the USB stream.
With the current `micropython/uartbone_bridge.py`, send the idle escape sequence
to stop the bridge and return to a normal MicroPython REPL without resetting the
RP2350:

```sh
python3 tools/stop_uartbone_bridge.py --port /dev/ttyACM0
```

Installing `micropython/uartbone_main.py` as `main.py` is possible for
standalone experiments, but it is not the default Forgix test flow. On this
board, resetting the RP2350 can disturb the FPGA configuration, so the
recommended path is to load the FPGA first and then start the bridge with the
host helper above.

If the board is running an older bridge without the idle escape handler, return
the RP2350 to the normal MicroPython REPL with a board reset:

```sh
mpremote connect /dev/ttyACM0 reset
```

## Graphical Host Demo

The DearPyGui host demo talks only to the LiteX TCP server. Start
`litex_server` as shown above, then run:

```sh
python3 host/forgix_gui.py --csr-csv build/adiuvo_forgix/csr.csv
```

The GUI reads the identifier, exercises the scratch CSR, monitors bus errors
and access latency, and drives the RGB LEDs. When the `--with-demo-leds`
gateware is loaded, it also exposes the hardware demo mode, RGB mask, speed,
and counter.

With the richer demo bitstream, the GUI also exposes:

- direct RGB PWM duty-cycle sliders and PWM period control,
- pattern and manual trigger controls,
- edge-connector output mask/value controls for the Teensy-style pins,
- integrated LiteScope captures of LED/pattern signals and SPIBone bus
  transactions through the same RP2350 UARTBone bridge.

The GUI can also start `litex_server` itself:

```sh
python3 host/forgix_gui.py \
    --csr-csv build/adiuvo_forgix_demo/csr.csv \
    --analyzer-csv build/adiuvo_forgix_demo/analyzer.csv \
    --start-server \
    --uart-port /dev/ttyACM0
```

## Loader Notes

The MicroPython loader uses passive SPI width 1, SPI mode 3, `OSC_EN` before
programming, `SS_N` low before releasing `CRESET_N`, `SS_N` held low through
the transfer, and 32 extra zero bytes after the bitstream.

The run aborts if `DONE` does not go high or if `STATUS` is low after
configuration.

The documented fast path uses a host-generated `.bin` decoded from the Efinity
`.hex` file. The loader can still use the generated `.hex` file directly when
the `.bin` file is not present.
