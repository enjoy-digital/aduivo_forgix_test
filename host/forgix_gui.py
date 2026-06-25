#!/usr/bin/env python3

#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import os
import socket
import subprocess
import sys
import time

# Constants ----------------------------------------------------------------------------------------


DEFAULT_HOST          = "localhost"
DEFAULT_PORT          = 1234
DEFAULT_UART_BAUDRATE = 1000000
DEFAULT_ADDR_WIDTH    = 32

DEFAULT_CSR_CSVS = (
    "build/adiuvo_forgix_demo/csr.csv",
    "build/adiuvo_forgix/csr.csv",
    "csr.csv",
)

LED_VALUES = (
    ("Off",     0x0),
    ("Red",     0x1),
    ("Green",   0x2),
    ("Yellow",  0x3),
    ("Blue",    0x4),
    ("Magenta", 0x5),
    ("Cyan",    0x6),
    ("White",   0x7),
)

DEMO_MODES = (
    ("Fixed",   0),
    ("Breathe", 1),
    ("Chase",   2),
    ("Rainbow", 3),
)

# LiteX Helpers ------------------------------------------------------------------------------------


def default_csr_csv():
    for path in DEFAULT_CSR_CSVS:
        if os.path.exists(path):
            return path
    return DEFAULT_CSR_CSVS[-1]


def get_reg(bus, name):
    return getattr(getattr(bus, "regs", object()), name, None)


def has_reg(bus, name):
    return get_reg(bus, name) is not None


def read_reg(bus, name, default=None):
    reg = get_reg(bus, name)
    if reg is None:
        return default
    return reg.read()


def write_reg(bus, name, value):
    reg = get_reg(bus, name)
    if reg is None:
        return False
    reg.write(value & 0xffffffff)
    return True


def detect_capabilities(bus):
    bases = getattr(bus, "bases", object())
    return {
        "identifier"   : hasattr(bases, "identifier_mem"),
        "scratch"      : has_reg(bus, "ctrl_scratch"),
        "bus_errors"   : has_reg(bus, "ctrl_bus_errors"),
        "leds"         : has_reg(bus, "leds_out"),
        "demo_core"    : all(has_reg(bus, name) for name in ("demo_leds_mode", "demo_leds_rgb", "demo_leds_speed")),
        "demo_counter" : has_reg(bus, "demo_leds_counter"),
    }


def read_identifier(bus, max_chars=256):
    bases = getattr(bus, "bases", object())
    if not hasattr(bases, "identifier_mem"):
        return ""

    chars = []
    for i in range(max_chars):
        value = bus.read(bases.identifier_mem + 4*i) & 0xff
        if value == 0:
            break
        chars.append(chr(value))
    return "".join(chars)


def scratch_roundtrip(bus, value=0x12345678):
    reg = get_reg(bus, "ctrl_scratch")
    if reg is None:
        raise RuntimeError("ctrl_scratch CSR is unavailable")

    original = reg.read()
    try:
        reg.write(value)
        readback = reg.read()
    finally:
        reg.write(original)
    return original, readback


def set_led(bus, value):
    value &= 0x7
    if write_reg(bus, "leds_out", value):
        return True

    if detect_capabilities(bus)["demo_core"]:
        write_reg(bus, "demo_leds_rgb", value)
        write_reg(bus, "demo_leds_mode", 0)
        return True

    return False


def set_demo(bus, mode=None, rgb=None, speed=None):
    if not detect_capabilities(bus)["demo_core"]:
        return False

    if rgb is not None:
        write_reg(bus, "demo_leds_rgb", rgb & 0x7)
    if speed is not None:
        write_reg(bus, "demo_leds_speed", speed & 0xff)
    if mode is not None:
        write_reg(bus, "demo_leds_mode", mode & 0x3)
    return True


def iter_registers(bus):
    regs = getattr(bus, "regs", object())
    items = []
    for name, reg in getattr(regs, "__dict__", {}).items():
        if hasattr(reg, "addr") and hasattr(reg, "read"):
            items.append((reg.addr, name, reg))
    return sorted(items)

# Server Helpers -----------------------------------------------------------------------------------


def start_litex_server(
    uart_port,
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    uart_baudrate=DEFAULT_UART_BAUDRATE,
    addr_width=DEFAULT_ADDR_WIDTH,
):
    if uart_port is None:
        raise ValueError("--uart-port is required when --start-server is used")

    command = [
        sys.executable,
        "-m", "litex.tools.litex_server",
        "--uart",
        "--uart-port", uart_port,
        "--uart-baudrate", str(uart_baudrate),
        "--addr-width", str(addr_width),
        "--bind-ip", host,
        "--bind-port", str(port),
    ]
    process = subprocess.Popen(command)
    wait_for_tcp(host, port)
    return process


def wait_for_tcp(host, port, timeout=5.0):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError as error:
            last_error = error
            time.sleep(0.1)
    raise TimeoutError("LiteX server did not open %s:%s: %s" % (host, port, last_error))


def stop_process(process):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)

# GUI ------------------------------------------------------------------------------------------------


def open_remote_client(host=DEFAULT_HOST, port=DEFAULT_PORT, csr_csv=None):
    from litex import RemoteClient

    bus = RemoteClient(host=host, port=port, csr_csv=csr_csv)
    bus.open()
    return bus


def run_gui(
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    csr_csv=None,
    start_server=False,
    uart_port=None,
    uart_baudrate=DEFAULT_UART_BAUDRATE,
    addr_width=DEFAULT_ADDR_WIDTH,
):
    import dearpygui.dearpygui as dpg

    server_process = None
    bus = None
    if csr_csv is None:
        csr_csv = default_csr_csv()

    try:
        if start_server:
            server_process = start_litex_server(
                uart_port      = uart_port,
                host           = host,
                port           = port,
                uart_baudrate  = uart_baudrate,
                addr_width     = addr_width,
            )

        bus = open_remote_client(host=host, port=port, csr_csv=csr_csv)
        caps = detect_capabilities(bus)
        identifier = read_identifier(bus) if caps["identifier"] else "LiteX target"
        registers = iter_registers(bus)

        samples = {
            "time"    : [],
            "counter" : [],
            "latency" : [],
        }
        started = time.time()
        last_poll = 0
        last_reg_poll = 0

        def log(message):
            dpg.set_value("status_log", "%s\n%s" % (time.strftime("%H:%M:%S"), message))

        def set_text(tag, value):
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, value)

        def on_led(sender, app_data, user_data):
            if set_led(bus, user_data):
                log("LEDs set to 0x%x" % user_data)
            else:
                log("No LED CSR is available")

        def on_demo_mode(sender, app_data):
            mode = dict(DEMO_MODES)[app_data]
            set_demo(bus, mode=mode)
            log("Demo mode set to %s" % app_data)

        def on_demo_rgb(sender, app_data):
            set_demo(bus, rgb=app_data)

        def on_demo_speed(sender, app_data):
            set_demo(bus, speed=app_data)

        def on_scratch(sender, app_data):
            try:
                original, readback = scratch_roundtrip(bus)
                if readback == 0x12345678:
                    log("Scratch OK, restored 0x%08x" % original)
                else:
                    log("Scratch mismatch: read 0x%08x" % readback)
            except Exception as error:
                log("Scratch failed: %s" % error)

        def on_register_write(sender, app_data, user_data):
            try:
                user_data.write(int(app_data, 0) & 0xffffffff)
                log("Wrote %s = %s" % (sender, app_data))
            except Exception as error:
                log("Write failed: %s" % error)

        def poll():
            nonlocal last_poll, last_reg_poll

            now = time.time()
            if now - last_poll < 0.10:
                return
            last_poll = now

            try:
                start = time.perf_counter()
                scratch = read_reg(bus, "ctrl_scratch", 0)
                latency_ms = (time.perf_counter() - start) * 1000.0
                bus_errors = read_reg(bus, "ctrl_bus_errors", 0)
                counter = read_reg(bus, "demo_leds_counter", 0) if caps["demo_counter"] else 0

                set_text("scratch_value", "0x%08x" % scratch)
                set_text("bus_errors_value", "0x%08x" % bus_errors)
                set_text("counter_value", "0x%08x" % counter)
                set_text("latency_value", "%.2f ms" % latency_ms)

                x = now - started
                samples["time"].append(x)
                samples["latency"].append(latency_ms)
                samples["counter"].append(counter)
                for key in samples:
                    samples[key] = samples[key][-160:]

                dpg.set_value("latency_series", [samples["time"], samples["latency"]])
                if caps["demo_counter"]:
                    dpg.set_value("counter_series", [samples["time"], samples["counter"]])

                if now - last_reg_poll >= 0.5:
                    last_reg_poll = now
                    for _, name, reg in registers:
                        try:
                            set_text("reg_value_%s" % name, "0x%08x" % reg.read())
                        except Exception:
                            set_text("reg_value_%s" % name, "read error")

            except Exception as error:
                log("Poll failed: %s" % error)

        dpg.create_context()
        dpg.create_viewport(title="Forgix LiteX Host", width=1180, height=760)
        dpg.setup_dearpygui()

        with dpg.window(tag="primary", label="Forgix LiteX Host", width=1180, height=760):
            dpg.add_text(identifier, tag="identifier_value")

            with dpg.group(horizontal=True):
                dpg.add_button(label="Scratch Test", callback=on_scratch)
                dpg.add_text("Scratch:")
                dpg.add_text("--", tag="scratch_value")
                dpg.add_text("Bus Errors:")
                dpg.add_text("--", tag="bus_errors_value")
                dpg.add_text("Latency:")
                dpg.add_text("--", tag="latency_value")

            dpg.add_separator()
            dpg.add_text("RGB LEDs")
            with dpg.group(horizontal=True):
                for label, value in LED_VALUES:
                    dpg.add_button(label=label, callback=on_led, user_data=value, width=78)

            if caps["demo_core"]:
                dpg.add_separator()
                dpg.add_text("Hardware Demo Core")
                with dpg.group(horizontal=True):
                    dpg.add_combo(
                        [name for name, _ in DEMO_MODES],
                        label="Mode",
                        default_value="Breathe",
                        callback=on_demo_mode,
                        width=130,
                    )
                    dpg.add_slider_int(label="RGB", min_value=0, max_value=7, default_value=7, callback=on_demo_rgb, width=180)
                    dpg.add_slider_int(label="Speed", min_value=0, max_value=255, default_value=8, callback=on_demo_speed, width=220)
                    dpg.add_text("Counter:")
                    dpg.add_text("--", tag="counter_value")
            else:
                dpg.add_text("Hardware Demo Core: unavailable")

            dpg.add_separator()
            with dpg.group(horizontal=True):
                with dpg.plot(label="Bus Read Latency", height=220, width=540):
                    dpg.add_plot_axis(dpg.mvXAxis, tag="latency_x", label="Time (s)")
                    with dpg.plot_axis(dpg.mvYAxis, tag="latency_y", label="Latency (ms)"):
                        dpg.add_line_series([], [], tag="latency_series")
                if caps["demo_counter"]:
                    with dpg.plot(label="Demo Counter", height=220, width=540):
                        dpg.add_plot_axis(dpg.mvXAxis, tag="counter_x", label="Time (s)")
                        with dpg.plot_axis(dpg.mvYAxis, tag="counter_y", label="Counter"):
                            dpg.add_line_series([], [], tag="counter_series")

            dpg.add_separator()
            dpg.add_text("Registers")
            with dpg.table(header_row=True, resizable=True, policy=dpg.mvTable_SizingStretchProp, height=230):
                dpg.add_table_column(label="Name")
                dpg.add_table_column(label="Address")
                dpg.add_table_column(label="Value")
                dpg.add_table_column(label="Write")
                for address, name, reg in registers:
                    with dpg.table_row():
                        dpg.add_text(name)
                        dpg.add_text("0x%08x" % address)
                        dpg.add_text("--", tag="reg_value_%s" % name)
                        dpg.add_input_text(
                            label="",
                            width=120,
                            on_enter=True,
                            callback=on_register_write,
                            user_data=reg,
                        )

            dpg.add_separator()
            dpg.add_text("", tag="status_log")

        dpg.set_primary_window("primary", True)
        dpg.show_viewport()
        log("Connected through LiteX server on %s:%s" % (host, port))

        while dpg.is_dearpygui_running():
            poll()
            dpg.render_dearpygui_frame()

    finally:
        try:
            if bus is not None:
                bus.close()
        finally:
            stop_process(server_process)
            try:
                dpg.destroy_context()
            except Exception:
                pass

# Run ----------------------------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="Forgix LiteX DearPyGui host demo.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="LiteX server host.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="LiteX server TCP port.")
    parser.add_argument("--csr-csv", default=default_csr_csv(), help="LiteX csr.csv path.")
    parser.add_argument("--start-server", action="store_true", help="Start litex_server before opening the GUI.")
    parser.add_argument("--uart-port", default=None, help="UART port for --start-server.")
    parser.add_argument("--uart-baudrate", default=DEFAULT_UART_BAUDRATE, type=int, help="UART baudrate for --start-server.")
    parser.add_argument("--addr-width", default=DEFAULT_ADDR_WIDTH, type=int, help="LiteX bus address width.")
    args = parser.parse_args(argv)

    run_gui(
        host          = args.host,
        port          = args.port,
        csr_csv       = args.csr_csv,
        start_server  = args.start_server,
        uart_port     = args.uart_port,
        uart_baudrate = args.uart_baudrate,
        addr_width    = args.addr_width,
    )


if __name__ == "__main__":
    main()
