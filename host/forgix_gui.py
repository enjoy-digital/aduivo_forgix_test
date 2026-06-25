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

DEFAULT_ANALYZER_CSVS = (
    "build/adiuvo_forgix_demo/analyzer.csv",
    "build/adiuvo_forgix/analyzer.csv",
    "analyzer.csv",
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
    ("Direct PWM", 0),
    ("Breathe",    1),
    ("Chase",      2),
    ("Rainbow",    3),
    ("Strobe",     4),
    ("Sparkle",    5),
)

# LiteX Helpers ------------------------------------------------------------------------------------


def default_csr_csv():
    for path in DEFAULT_CSR_CSVS:
        if os.path.exists(path):
            return path
    return DEFAULT_CSR_CSVS[-1]


def default_analyzer_csv(csr_csv=None):
    candidates = []
    if csr_csv:
        candidates.append(os.path.join(os.path.dirname(csr_csv), "analyzer.csv"))
    candidates += list(DEFAULT_ANALYZER_CSVS)
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return candidates[0] if candidates else DEFAULT_ANALYZER_CSVS[-1]


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


def detect_capabilities(bus, analyzer_csv=None):
    bases = getattr(bus, "bases", object())
    return {
        "identifier"   : hasattr(bases, "identifier_mem"),
        "scratch"      : has_reg(bus, "ctrl_scratch"),
        "bus_errors"   : has_reg(bus, "ctrl_bus_errors"),
        "leds"         : has_reg(bus, "leds_out"),
        "demo_core"    : all(has_reg(bus, name) for name in ("demo_leds_mode", "demo_leds_rgb", "demo_leds_speed")),
        "demo_counter" : has_reg(bus, "demo_leds_counter"),
        "demo_pwm"     : all(has_reg(bus, name) for name in ("demo_leds_pwm_r", "demo_leds_pwm_g", "demo_leds_pwm_b", "demo_leds_pwm_period")),
        "demo_pattern" : all(has_reg(bus, name) for name in ("demo_leds_pattern", "demo_leds_trigger")),
        "demo_gpio"    : all(has_reg(bus, name) for name in ("demo_leds_gpio_mask", "demo_leds_gpio_value")),
        "demo_status"  : all(has_reg(bus, name) for name in ("demo_leds_status", "demo_leds_frame_counter", "demo_leds_event_counter")),
        "litescope"    : has_reg(bus, "analyzer_storage_enable") and analyzer_csv is not None and os.path.exists(analyzer_csv),
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
        write_reg(bus, "demo_leds_mode", mode & 0x7)
    return True


def set_demo_pwm(bus, r=None, g=None, b=None, period=None):
    if not detect_capabilities(bus)["demo_pwm"]:
        return False

    values = (
        ("demo_leds_pwm_r", r),
        ("demo_leds_pwm_g", g),
        ("demo_leds_pwm_b", b),
        ("demo_leds_pwm_period", period),
    )
    for name, value in values:
        if value is not None:
            write_reg(bus, name, int(value) & 0xff)
    return True


def set_demo_pattern(bus, pattern=None, trigger=False):
    if not detect_capabilities(bus)["demo_pattern"]:
        return False

    if pattern is not None:
        write_reg(bus, "demo_leds_pattern", int(pattern) & 0xf)
    if trigger:
        write_reg(bus, "demo_leds_trigger", 1)
    return True


def set_demo_gpio(bus, mask=None, value=None):
    if not detect_capabilities(bus)["demo_gpio"]:
        return False

    if mask is not None:
        write_reg(bus, "demo_leds_gpio_mask", int(mask) & 0x3ffff)
    if value is not None:
        write_reg(bus, "demo_leds_gpio_value", int(value) & 0x3ffff)
    return True


def read_demo_status(bus):
    return {
        "status"        : read_reg(bus, "demo_leds_status", 0),
        "frame_counter" : read_reg(bus, "demo_leds_frame_counter", 0),
        "event_counter" : read_reg(bus, "demo_leds_event_counter", 0),
    }


def iter_registers(bus):
    regs = getattr(bus, "regs", object())
    items = []
    for name, reg in getattr(regs, "__dict__", {}).items():
        if hasattr(reg, "addr") and hasattr(reg, "read"):
            items.append((reg.addr, name, reg))
    return sorted(items)


def capture_litescope(bus, analyzer_csv, group=0, length=128, subsampling=1, trigger=None, driver_cls=None):
    if driver_cls is None:
        from litescope import LiteScopeAnalyzerDriver
        driver_cls = LiteScopeAnalyzerDriver

    basename = os.path.splitext(os.path.basename(analyzer_csv))[0]
    analyzer = driver_cls(bus.regs, basename, config_csv=analyzer_csv, debug=False)
    analyzer.configure_group(int(group))
    analyzer.configure_subsampler(int(subsampling))
    if hasattr(analyzer, "configure_rle"):
        analyzer.configure_rle(False)
    if trigger:
        analyzer.add_trigger(cond=trigger)
    else:
        analyzer.configure_trigger()
    analyzer.run(offset=0, length=int(length))
    analyzer.wait_done(delay=0.02)
    data = analyzer.upload(max_samples=int(length))
    return analyzer, list(data)


def waveform_series(samples, layout, max_signals=8):
    series = []
    bit_offset = 0
    for name, width in layout[:max_signals]:
        mask = (1 << width) - 1
        values = [((sample >> bit_offset) & mask) for sample in samples]
        scale = mask if mask else 1
        row = len(series)
        y_values = [row + (value / scale if scale else 0) * 0.8 for value in values]
        series.append((name, list(range(len(samples))), y_values))
        bit_offset += width
    return series

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
    analyzer_csv=None,
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
    if analyzer_csv is None:
        analyzer_csv = default_analyzer_csv(csr_csv)

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
        caps = detect_capabilities(bus, analyzer_csv=analyzer_csv)
        identifier = read_identifier(bus) if caps["identifier"] else "LiteX target"
        registers = iter_registers(bus)

        samples = {
            "time"    : [],
            "counter" : [],
            "latency" : [],
            "frame"   : [],
            "event"   : [],
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

        def on_pwm(sender, app_data, user_data):
            set_demo_pwm(bus, **{user_data: app_data})

        def on_pattern(sender, app_data):
            set_demo_pattern(bus, pattern=app_data)

        def on_manual_trigger(sender, app_data):
            set_demo_pattern(bus, trigger=True)
            log("Manual demo trigger")

        def on_gpio(sender, app_data, user_data):
            try:
                value = int(app_data, 0)
                set_demo_gpio(bus, **{user_data: value})
                log("GPIO %s = 0x%05x" % (user_data, value & 0x3ffff))
            except ValueError as error:
                log("GPIO value rejected: %s" % error)

        def on_scope_capture(sender, app_data, user_data):
            try:
                length = int(dpg.get_value("scope_length"))
                subsampling = int(dpg.get_value("scope_subsampling"))
                analyzer, captured = capture_litescope(
                    bus          = bus,
                    analyzer_csv = analyzer_csv,
                    group        = user_data,
                    length       = length,
                    subsampling  = subsampling,
                )
                layout = analyzer.layouts.get(analyzer.group, [])
                decoded = waveform_series(captured, layout, max_signals=8)
                for index in range(8):
                    label_tag = "scope_label_%u" % index
                    series_tag = "scope_series_%u" % index
                    if index < len(decoded):
                        name, x_values, y_values = decoded[index]
                        set_text(label_tag, "%u: %s" % (index, name))
                        dpg.set_value(series_tag, [x_values, y_values])
                    else:
                        set_text(label_tag, "%u:" % index)
                        dpg.set_value(series_tag, [[], []])
                log("Captured %u LiteScope samples from group %u" % (len(captured), user_data))
            except Exception as error:
                log("LiteScope capture failed: %s" % error)

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
                demo_status = read_demo_status(bus) if caps["demo_status"] else {}

                set_text("scratch_value", "0x%08x" % scratch)
                set_text("bus_errors_value", "0x%08x" % bus_errors)
                set_text("counter_value", "0x%08x" % counter)
                set_text("frame_counter_value", "0x%08x" % demo_status.get("frame_counter", 0))
                set_text("event_counter_value", "0x%08x" % demo_status.get("event_counter", 0))
                set_text("demo_status_value", "0x%02x" % demo_status.get("status", 0))
                set_text("latency_value", "%.2f ms" % latency_ms)

                x = now - started
                samples["time"].append(x)
                samples["latency"].append(latency_ms)
                samples["counter"].append(counter)
                samples["frame"].append(demo_status.get("frame_counter", 0))
                samples["event"].append(demo_status.get("event_counter", 0))
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
                dpg.add_text("LED Lab")
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
                if caps["demo_pwm"]:
                    with dpg.group(horizontal=True):
                        dpg.add_slider_int(label="R Duty", min_value=0, max_value=255, default_value=255, callback=on_pwm, user_data="r", width=170)
                        dpg.add_slider_int(label="G Duty", min_value=0, max_value=255, default_value=255, callback=on_pwm, user_data="g", width=170)
                        dpg.add_slider_int(label="B Duty", min_value=0, max_value=255, default_value=255, callback=on_pwm, user_data="b", width=170)
                        dpg.add_slider_int(label="PWM Top", min_value=1, max_value=255, default_value=255, callback=on_pwm, user_data="period", width=170)
                if caps["demo_pattern"]:
                    with dpg.group(horizontal=True):
                        dpg.add_slider_int(label="Pattern", min_value=0, max_value=15, default_value=0, callback=on_pattern, width=180)
                        dpg.add_button(label="Trigger", callback=on_manual_trigger, width=90)
                if caps["demo_status"]:
                    with dpg.group(horizontal=True):
                        dpg.add_text("Status:")
                        dpg.add_text("--", tag="demo_status_value")
                        dpg.add_text("Frames:")
                        dpg.add_text("--", tag="frame_counter_value")
                        dpg.add_text("Events:")
                        dpg.add_text("--", tag="event_counter_value")
            else:
                dpg.add_text("Hardware Demo Core: unavailable")

            if caps["demo_gpio"]:
                dpg.add_separator()
                dpg.add_text("Edge IO")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(label="Mask", default_value="0x00000", on_enter=True, callback=on_gpio, user_data="mask", width=160)
                    dpg.add_input_text(label="Value", default_value="0x00000", on_enter=True, callback=on_gpio, user_data="value", width=160)

            if caps["litescope"]:
                dpg.add_separator()
                dpg.add_text("LiteScope")
                with dpg.group(horizontal=True):
                    dpg.add_input_int(label="Samples", tag="scope_length", default_value=128, min_value=1, max_value=512, width=120)
                    dpg.add_input_int(label="Subsampling", tag="scope_subsampling", default_value=1, min_value=1, max_value=65536, width=120)
                    dpg.add_button(label="Capture LED", callback=on_scope_capture, user_data=0, width=100)
                    dpg.add_button(label="Capture Bus", callback=on_scope_capture, user_data=1, width=100)
                with dpg.group(horizontal=True):
                    with dpg.group():
                        for index in range(8):
                            dpg.add_text("%u:" % index, tag="scope_label_%u" % index)
                    with dpg.plot(label="LiteScope Capture", height=220, width=860):
                        dpg.add_plot_axis(dpg.mvXAxis, tag="scope_x", label="Sample")
                        with dpg.plot_axis(dpg.mvYAxis, tag="scope_y", label="Signal"):
                            for index in range(8):
                                dpg.add_line_series([], [], tag="scope_series_%u" % index)

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
    parser.add_argument("--analyzer-csv", default=None, help="LiteScope analyzer.csv path.")
    parser.add_argument("--start-server", action="store_true", help="Start litex_server before opening the GUI.")
    parser.add_argument("--uart-port", default=None, help="UART port for --start-server.")
    parser.add_argument("--uart-baudrate", default=DEFAULT_UART_BAUDRATE, type=int, help="UART baudrate for --start-server.")
    parser.add_argument("--addr-width", default=DEFAULT_ADDR_WIDTH, type=int, help="LiteX bus address width.")
    args = parser.parse_args(argv)

    run_gui(
        host          = args.host,
        port          = args.port,
        csr_csv       = args.csr_csv,
        analyzer_csv  = args.analyzer_csv,
        start_server  = args.start_server,
        uart_port     = args.uart_port,
        uart_baudrate = args.uart_baudrate,
        addr_width    = args.addr_width,
    )


if __name__ == "__main__":
    main()
