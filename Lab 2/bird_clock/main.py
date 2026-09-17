"""Bird clock entry point. Picks the Pi screen when Blinka is importable.

On the Pi (venv with Lab 2 requirements.txt):
    cd ~/Interactive-Lab-Hub/Lab\\ 2
    python3 -m bird_clock

On a laptop (tkinter window):
    python3 -m bird_clock --desktop

Buttons: GPIO 23 (top) = start / retry.  GPIO 24 (bottom) = hold to flap.
Desktop keys: A / Enter = start.  S / Space = hold to flap.  Esc = quit.
"""

import argparse
import time

from .config import DEFAULT
from .game import Game
from .renderer import Renderer


def _make_backend(force: str):
    """Return (display, buttons, name). force is 'auto', 'pi', or 'desktop'."""
    if force != "desktop":
        try:
            from .hardware import Buttons, Display

            display = Display(DEFAULT)
            return display, Buttons(DEFAULT), "pi"
        except Exception as exc:  # no Blinka, no SPI, or not a Pi
            if force == "pi":
                raise
            print(f"[bird_clock] Pi screen unavailable ({exc}); using desktop window.")

    from .desktop import DesktopButtons, DesktopDisplay

    display = DesktopDisplay(DEFAULT)
    return display, DesktopButtons(display), "desktop"


def main():
    parser = argparse.ArgumentParser(description="Flappy-style bird clock.")
    backend = parser.add_mutually_exclusive_group()
    backend.add_argument("--pi", action="store_true", help="force the MiniPiTFT screen")
    backend.add_argument("--desktop", action="store_true", help="force the laptop window")
    parser.add_argument("--fps", type=float, default=DEFAULT.loop.fps)
    args = parser.parse_args()

    force = "pi" if args.pi else "desktop" if args.desktop else "auto"
    config = DEFAULT
    display, buttons, name = _make_backend(force)
    print(f"[bird_clock] backend: {name}")

    game = Game(config)
    renderer = Renderer(display, config)

    frame_s = 1.0 / max(args.fps, 1.0)
    last = time.monotonic()

    try:
        while not display.closed:
            now = time.monotonic()
            dt = min(now - last, 0.1)
            last = now

            buttons.poll()
            game.handle_input(
                start_pressed=buttons.start_pressed,
                flap_pressed=buttons.flap_pressed,
                flap_held=buttons.flap_held,
            )
            game.update(dt)
            renderer.draw(game)
            display.pump()

            spent = time.monotonic() - now
            if spent < frame_s:
                time.sleep(frame_s - spent)
    except KeyboardInterrupt:
        pass
    finally:
        close = getattr(display, "close", None)
        if close is not None:
            close()


if __name__ == "__main__":
    main()
