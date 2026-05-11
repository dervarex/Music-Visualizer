import sys
import subprocess
import threading

if sys.platform.startswith("win"):
    print("[error] Windows is not supported by this script.")
    print("[error] This overlay requires GTK/GtkLayerShell on Linux.")
    sys.exit(1)

import gi
import numpy as np

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, Gdk

# try layer shell

LAYER_SHELL = False

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    LAYER_SHELL = True
except Exception:
    print("[warn] gtk-layer-shell not found")
    print("[warn] overlay mode unsupported on this desktop")

#            #
##          ##
### CONFIG ###
##          ##
#            #

BAR_HEIGHT = 4
FPS = 60

# audio shaping

AUDIO_GAIN = 4.5
NOISE_FLOOR = 0.010
FULL_SCALE = 0.55
GAMMA = 1.8

# one smoothing value
SMOOTHING = 0.18

level = 0.0

# detect backend

display = Gdk.Display.get_default()
backend = "unknown"

if display:
    name = display.__class__.__name__.lower()

    if "wayland" in name:
        backend = "wayland"
    elif "x11" in name:
        backend = "x11"

print(f"[info] backend: {backend}")

if backend == "x11":
    print("[warn] x11 detected, clickthrough may not work correctly")
elif backend == "unknown":
    print("[warn] unknown display backend")

# audio source detection

def get_default_monitor():
    try:
        sink = subprocess.check_output(
            ["pactl", "get-default-sink"],
            text=True
        ).strip()

        if sink:
            return sink + ".monitor"

    except Exception as e:
        print("[warn] pactl get-default-sink failed")
        print(e)

    try:
        info = subprocess.check_output(
            ["pactl", "info"],
            text=True
        )

        for line in info.splitlines():
            if line.startswith("Default Sink:"):
                sink = line.split(":", 1)[1].strip()
                if sink:
                    return sink + ".monitor"

    except Exception as e:
        print("[warn] pactl info fallback failed")
        print(e)

    print("[error] could not detect default audio monitor")
    return None


MONITOR_SOURCE = get_default_monitor()

if not MONITOR_SOURCE:
    sys.exit(1)

print(f"[info] monitor source: {MONITOR_SOURCE}")

# window

win = Gtk.Window()

win.set_decorated(False)
win.set_resizable(False)
win.set_accept_focus(False)
win.set_focus_on_map(False)
win.set_skip_taskbar_hint(True)
win.set_skip_pager_hint(True)
win.set_app_paintable(True)

screen = win.get_screen()
visual = screen.get_rgba_visual()

if visual and screen.is_composited():
    win.set_visual(visual)

# layer shell setup

if LAYER_SHELL:
    GtkLayerShell.init_for_window(win)

    GtkLayerShell.set_layer(
        win,
        GtkLayerShell.Layer.TOP
    )

    GtkLayerShell.set_anchor(
        win,
        GtkLayerShell.Edge.LEFT,
        True
    )
    GtkLayerShell.set_anchor(
        win,
        GtkLayerShell.Edge.RIGHT,
        True
    )
    GtkLayerShell.set_anchor(
        win,
        GtkLayerShell.Edge.BOTTOM,
        True
    )

    GtkLayerShell.set_margin(
        win,
        GtkLayerShell.Edge.BOTTOM,
        0
    )

    GtkLayerShell.set_exclusive_zone(
        win,
        0
    )

    try:
        GtkLayerShell.set_keyboard_mode(
            win,
            GtkLayerShell.KeyboardMode.NONE
        )
    except Exception:
        pass
else:
    print("[warn] running without layer shell")
    print("[warn] overlay positioning unsupported")

# makes the overlay click through

def make_clickthrough(widget):
    gdk_window = widget.get_window()

    if gdk_window:
        try:
            gdk_window.set_pass_through(True)
        except Exception:
            print("[warn] clickthrough unsupported")

win.connect("realize", make_clickthrough)

# draw area

area = Gtk.DrawingArea()
area.set_size_request(-1, BAR_HEIGHT)
win.add(area)

def draw(widget, cr):
    width = widget.get_allocated_width()
    height = widget.get_allocated_height()

    # transparency
    cr.set_operator(0)
    cr.paint()

    cr.set_operator(2)


    visual_level = max(0.0, min(1.0, level))
    visual_level = visual_level ** 2.0

    line_width = max(
        8,
        visual_level * width * 0.98
    )

    x = (width - line_width) / 2

    r = 0.25 + visual_level * 0.35
    g = 0.75 + visual_level * 0.20
    b = 1.0

    # main bar
    cr.set_source_rgba(r, g, b, 1.0)
    cr.rectangle(x, 0, line_width, 2)
    cr.fill()

    # glow
    if height > 2:
        cr.set_source_rgba(r, g, b, 0.22)
        cr.rectangle(x, 2, line_width, 2)
        cr.fill()

    return False

area.connect("draw", draw)

# audio capture

def get_level_from_samples(samples):
    rms = float(np.sqrt(np.mean(samples * samples)))


    rms *= AUDIO_GAIN


    if rms <= NOISE_FLOOR:
        return 0.0


    normalized = (rms - NOISE_FLOOR) / (FULL_SCALE - NOISE_FLOOR)
    normalized = max(0.0, min(1.0, normalized))

    
    shaped = normalized ** GAMMA

    return shaped


def audio_thread():
    global level

    cmd = [
        "ffmpeg",
        "-loglevel", "quiet",
        "-f", "pulse",
        "-i", MONITOR_SOURCE,
        "-ac", "1",
        "-ar", "44100",
        "-f", "s16le",
        "-"
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096
        )
    except FileNotFoundError:
        print("[error] ffmpeg not found")
        sys.exit(1)
    except Exception as e:
        print("[error] failed to start ffmpeg")
        print(e)
        sys.exit(1)

    if process.stdout is None:
        print("[error] ffmpeg stdout unavailable")
        sys.exit(1)

    CHUNK = 2048
    smooth = 0.0

    while True:
        raw = process.stdout.read(CHUNK * 2)

        if len(raw) < CHUNK * 2:
            continue

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        samples /= 32768.0

        target = get_level_from_samples(samples)

        smooth += (target - smooth) * SMOOTHING
        level = smooth


threading.Thread(
    target=audio_thread,
    daemon=True
).start()

# frame loop

def tick():
    area.queue_draw()
    return True

GLib.timeout_add(
    int(1000 / FPS),
    tick
)

# start

win.show_all()
print("[info] started")
Gtk.main()
