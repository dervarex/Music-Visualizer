# Audio Overlay Visualizer

Minimal audio reactive desktop visualizer for Linux using GTK Layer Shell and PulseAudio/PipeWire

## Features

* Audio reactive overlay
* Click-through
* Automatic audio device detection
* Works with PulseAudio and PipeWire
* Lightweight GTK3 renderer

## Requirements

* Linux
* Python 3
* GTK3
* gtk-layer-shell
* ffmpeg

## Install

### Arch Linux

```bash id="b8x0tn"
sudo pacman -S python python-gobject gtk-layer-shell ffmpeg
```

### Debian / Ubuntu

```bash id="v2n5qe"
sudo apt install python3 python3-gi ffmpeg libgtk-layer-shell-dev
```

## Run

```bash id="q4z9dk"
python main.py
```

## Notes

* Works best on Wayland
* X11 support is limited(the bar could not be clicktrough)
* Windows and macOS are not supported

## License

MIT, you are free to redistribue the code as long as you credit me
