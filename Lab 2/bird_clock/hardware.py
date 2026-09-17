"""MiniPiTFT + two buttons. Same wiring as Lab 2 screen_clock.py / screen_test.py."""

import digitalio
import board
from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import st7789

from .config import GameConfig


class Buttons:
    def __init__(self, config: GameConfig):
        cfg = config.buttons
        self._active_low = cfg.active_low
        self._start = digitalio.DigitalInOut(getattr(board, f"D{cfg.start_gpio}"))
        self._flap = digitalio.DigitalInOut(getattr(board, f"D{cfg.flap_gpio}"))
        self._start.switch_to_input(pull=digitalio.Pull.UP)
        self._flap.switch_to_input(pull=digitalio.Pull.UP)
        self._start_was = False
        self._flap_was = False
        self.start_held = False
        self.flap_held = False
        self.start_pressed = False
        self.flap_pressed = False

    def _held(self, pin) -> bool:
        value = pin.value
        return (not value) if self._active_low else bool(value)

    def poll(self):
        self.start_held = self._held(self._start)
        self.flap_held = self._held(self._flap)
        self.start_pressed = self.start_held and not self._start_was
        self.flap_pressed = self.flap_held and not self._flap_was
        self._start_was = self.start_held
        self._flap_was = self.flap_held


class Display:
    def __init__(self, config: GameConfig):
        screen = config.screen
        cs = digitalio.DigitalInOut(getattr(board, f"D{screen.cs_gpio}"))
        dc = digitalio.DigitalInOut(getattr(board, f"D{screen.dc_gpio}"))
        spi = board.SPI()
        self._disp = st7789.ST7789(
            spi,
            cs=cs,
            dc=dc,
            rst=None,
            baudrate=screen.baudrate,
            width=screen.panel_width,
            height=screen.panel_height,
            x_offset=screen.x_offset,
            y_offset=screen.y_offset,
        )
        self.rotation = screen.rotation
        self.width = screen.width
        self.height = screen.height
        self.image = Image.new("RGB", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        try:
            self.font = ImageFont.truetype(config.font_path, config.font_size)
        except OSError:
            self.font = ImageFont.load_default()
        self._backlight = digitalio.DigitalInOut(getattr(board, f"D{screen.backlight_gpio}"))
        self._backlight.switch_to_output(value=True)
        self.draw.rectangle((0, 0, self.width, self.height), fill=(0, 0, 0))
        self.show()

    def show(self):
        self._disp.image(self.image, self.rotation)

    def pump(self):
        return None

    @property
    def closed(self):
        return False

    def close(self):
        """Blank the panel so Ctrl-C does not leave the last frame on screen."""
        self.draw.rectangle((0, 0, self.width, self.height), fill=(0, 0, 0))
        try:
            self.show()
        finally:
            self._backlight.value = False
