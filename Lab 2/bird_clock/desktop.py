"""Laptop window that pretends to be the 240x135 PiTFT.

Keyboard:
  A / Return  = top button (start / retry)
  S / Space   = bottom button (hold to flap)
  Esc         = quit
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageTk

from .config import GameConfig

_START_KEYS = {"a", "A", "Return"}
_FLAP_KEYS = {"s", "S", "space"}
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
)


def _load_font(config: GameConfig):
    paths = (config.font_path,) + _FONT_CANDIDATES
    for path in paths:
        try:
            return ImageFont.truetype(path, config.font_size)
        except OSError:
            continue
    return ImageFont.load_default()


class DesktopDisplay:
    def __init__(self, config: GameConfig, scale: int = 2):
        self.rotation = 0
        self.width = config.screen.width
        self.height = config.screen.height
        self.image = Image.new("RGB", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        self.font = _load_font(config)
        self.scale = scale
        self.closed = False

        self._root = tk.Tk()
        self._root.title("bird_clock desktop  |  A/Enter start   S/Space flap (hold)   Esc quit")
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._root.bind("<KeyPress>", self._on_press)
        self._root.bind("<KeyRelease>", self._on_release)
        self._root.bind("<Escape>", lambda _e: self._close())

        self._held = set()
        self._label = tk.Label(self._root)
        self._label.pack()
        self._photo = None
        self._root.update_idletasks()

    def _close(self):
        self.closed = True
        try:
            self._root.destroy()
        except tk.TclError:
            pass

    def close(self):
        self._close()

    def _on_press(self, event):
        self._held.add(event.keysym)

    def _on_release(self, event):
        self._held.discard(event.keysym)

    def start_held(self) -> bool:
        return bool(self._held & _START_KEYS)

    def flap_held(self) -> bool:
        return bool(self._held & _FLAP_KEYS)

    def show(self):
        if self.closed:
            return
        scaled = self.image.resize(
            (self.width * self.scale, self.height * self.scale),
            Image.NEAREST,
        )
        self._photo = ImageTk.PhotoImage(scaled)
        self._label.configure(image=self._photo)

    def pump(self):
        if self.closed:
            return
        try:
            self._root.update()
        except tk.TclError:
            self.closed = True


class DesktopButtons:
    def __init__(self, display: DesktopDisplay):
        self._display = display
        self._start_was = False
        self._flap_was = False
        self.start_held = False
        self.flap_held = False
        self.start_pressed = False
        self.flap_pressed = False

    def poll(self):
        self.start_held = self._display.start_held()
        self.flap_held = self._display.flap_held()
        self.start_pressed = self.start_held and not self._start_was
        self.flap_pressed = self.flap_held and not self._flap_was
        self._start_was = self.start_held
        self._flap_was = self.flap_held
