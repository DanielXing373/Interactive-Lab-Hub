#!/usr/bin/env python3
"""
Raspberry Pi Card Vision capture + test loop.

Uses the course MiniPiTFT A/B buttons (same wiring as Interactive Lab Hub Lab 2):
  Button A (top,    GPIO23) — capture USB webcam frame, save image, run recognition
  Button B (bottom, GPIO24) — quit

Saved files land in ./captures/ so you can re-test later with:
  python3 run_card_vision.py --image captures/<timestamp>.jpg

Examples (run on the Pi):
  python3 pi_capture_test.py
  python3 pi_capture_test.py --camera 0 --show
  python3 pi_capture_test.py --keyboard          # no GPIO; press 'a' / 'q' in terminal
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2

import card_vision
from run_card_vision import draw_detections


# MiniPiTFT defaults from Interactive Lab Hub Lab 2
DEFAULT_BUTTON_A_GPIO = 23  # top button
DEFAULT_BUTTON_B_GPIO = 24  # bottom button


class ButtonInputs:
    """Edge-triggered A/B inputs: GPIO on Pi, or keyboard fallback."""

    def __init__(self, use_gpio: bool, gpio_a: int, gpio_b: int):
        self.mode = "keyboard"
        self._a = None
        self._b = None
        self._a_was = False
        self._b_was = False
        self.a_pressed = False
        self.b_pressed = False

        if use_gpio:
            try:
                import board
                import digitalio

                self._a = digitalio.DigitalInOut(getattr(board, f"D{gpio_a}"))
                self._b = digitalio.DigitalInOut(getattr(board, f"D{gpio_b}"))
                self._a.switch_to_input(pull=digitalio.Pull.UP)
                self._b.switch_to_input(pull=digitalio.Pull.UP)
                self.mode = "gpio"
                print(
                    f"GPIO buttons ready: A=D{gpio_a} (capture), B=D{gpio_b} (quit)",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"WARNING: GPIO buttons unavailable ({exc}). "
                    "Falling back to keyboard: 'a'=capture, 'q'=quit.",
                    file=sys.stderr,
                    flush=True,
                )

        if self.mode == "keyboard":
            print(
                "Keyboard mode: press 'a' then Enter to capture, 'q' then Enter to quit.",
                flush=True,
            )

    def _gpio_held(self, pin) -> bool:
        # Active-LOW with pull-up (pressed => False)
        return pin.value is False

    def poll(self):
        self.a_pressed = False
        self.b_pressed = False

        if self.mode == "gpio":
            a_held = self._gpio_held(self._a)
            b_held = self._gpio_held(self._b)
            self.a_pressed = a_held and not self._a_was
            self.b_pressed = b_held and not self._b_was
            self._a_was = a_held
            self._b_was = b_held
            return

        # Non-blocking-ish keyboard: only checks if stdin has a line waiting
        # when used with --keyboard on a TTY. For simplicity, blocking readline
        # is used in the main loop instead (see run_loop keyboard branch).


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def capture_and_recognize(frame, out_dir: str, args) -> list:
    """Save raw + annotated image, JSON result; return public detections."""
    detections = card_vision.detect_cards(
        frame,
        template_dir=args.templates,
        min_area=args.min_area,
        max_area=args.max_area,
        include_unknown=not args.skip_unknown,
    )
    exported = card_vision.export_capture(
        frame,
        detections=detections,
        out_dir=out_dir,
        verbose=args.verbose,
    )
    result = exported["detections"]

    print("=" * 50, flush=True)
    print(f"Saved:      {exported['image']}", flush=True)
    print(f"Annotated:  {exported['annotated']}", flush=True)
    print(f"JSON:       {exported['json']}", flush=True)
    print(json.dumps(result, indent=2), flush=True)
    print("=" * 50, flush=True)
    print("A = capture again | B = quit", flush=True)

    return result


def grab_fresh_frame(cap, flush_reads: int = 5):
    """Discard a few buffered frames so the capture is recent."""
    return card_vision.grab_frame(cap, flush_reads=flush_reads)

def run_gpio_loop(cap, buttons: ButtonInputs, out_dir: str, args, recorder=None):
    print("Ready. Press A to capture+recognize, B to quit.", flush=True)
    while True:
        # Keep reading frames while recording (or showing preview)
        preview = None
        if recorder is not None or args.show:
            ok, preview = cap.read()
            if ok and preview is not None and recorder is not None:
                recorder.write(preview)

        if args.show and preview is not None:
            cv2.imshow("Card Vision Pi (A=shot B=quit)", preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("a"), ord(" ")):
                frame = grab_fresh_frame(cap)
                if frame is not None:
                    capture_and_recognize(frame, out_dir, args)
            elif key in (ord("q"), ord("b")):
                break

        buttons.poll()
        if buttons.a_pressed:
            frame = grab_fresh_frame(cap)
            if frame is None:
                print("ERROR: camera read failed.", file=sys.stderr, flush=True)
            else:
                capture_and_recognize(frame, out_dir, args)
            time.sleep(0.2)
        if buttons.b_pressed:
            print("Quit (button B).", flush=True)
            break

        if recorder is None and not args.show:
            time.sleep(0.05)


def run_keyboard_loop(cap, out_dir: str, args, recorder=None):
    print("Type 'a' + Enter to capture, 'q' + Enter to quit.", flush=True)
    while True:
        if recorder is not None or args.show:
            ok, preview = cap.read()
            if ok and preview is not None and recorder is not None:
                recorder.write(preview)
            if args.show and preview is not None:
                cv2.imshow("Card Vision Pi (a=shot q=quit)", preview)
                key = cv2.waitKey(50) & 0xFF
                if key in (ord("a"), ord(" ")):
                    frame = grab_fresh_frame(cap)
                    if frame is not None:
                        capture_and_recognize(frame, out_dir, args)
                    continue
                if key in (ord("q"), ord("b")):
                    break

        # When recording without show, avoid blocking forever on input:
        # only prompt when not recording, otherwise use a short select-style poll.
        if recorder is not None and not args.show:
            # Non-interactive friendly: check stdin without long block
            import select

            readable, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not readable:
                continue
            line = sys.stdin.readline().strip().lower()
        else:
            try:
                line = input("> ").strip().lower()
            except EOFError:
                break

        if line in ("a", "capture", "shot", "p"):
            frame = grab_fresh_frame(cap)
            if frame is None:
                print("ERROR: camera read failed.", file=sys.stderr, flush=True)
            else:
                capture_and_recognize(frame, out_dir, args)
        elif line in ("q", "quit", "b", "exit"):
            print("Quit.", flush=True)
            break
        elif line:
            print("Commands: a = capture, q = quit", flush=True)


def build_parser():
    p = argparse.ArgumentParser(
        description="Pi USB webcam capture + card recognition (MiniPiTFT A/B buttons)."
    )
    p.add_argument("--camera", type=int, default=0, help="USB camera index (default 0)")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument(
        "--out-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures"),
        help="Directory for saved photos / JSON (default: ./captures)",
    )
    p.add_argument("--templates", default=None, help="Rank/suit template directory")
    p.add_argument("--min-area", type=int, default=None)
    p.add_argument("--max-area", type=int, default=None)
    p.add_argument("--skip-unknown", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--show",
        action="store_true",
        help="Show OpenCV preview window (needs display)",
    )
    p.add_argument(
        "--keyboard",
        action="store_true",
        help="Force keyboard control instead of GPIO A/B",
    )
    p.add_argument("--gpio-a", type=int, default=DEFAULT_BUTTON_A_GPIO)
    p.add_argument("--gpio-b", type=int, default=DEFAULT_BUTTON_B_GPIO)
    p.add_argument(
        "--record",
        action="store_true",
        help="Record a session video from start until B/quit",
    )
    p.add_argument(
        "--record-fps",
        type=float,
        default=10.0,
        help="Session recording FPS (default 10)",
    )
    p.add_argument(
        "--record-raw",
        action="store_true",
        help="Record without labels (labels only appear if you pass detections; "
        "this flag disables burn-in when detections are provided)",
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    out_dir = ensure_dir(args.out_dir)

    try:
        cap = card_vision.open_usb_camera(
            camera_index=args.camera,
            width=args.width,
            height=args.height,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Tip: try --camera 1 (or 2). Check lsusb / ls /dev/video*",
            file=sys.stderr,
        )
        return 1

    # Warm up + preload templates once
    time.sleep(0.5)
    grab_fresh_frame(cap, flush_reads=8)
    card_vision.load_templates(args.templates)
    print(f"Output directory: {out_dir}", flush=True)

    recorder = None
    if args.record:
        recorder = card_vision.start_session_recording(
            out_dir=out_dir,
            fps=args.record_fps,
            draw_labels=not args.record_raw,
        )
        print(f"Recording session -> {recorder.path}", flush=True)

    use_gpio = not args.keyboard
    buttons = ButtonInputs(use_gpio=use_gpio, gpio_a=args.gpio_a, gpio_b=args.gpio_b)

    try:
        if buttons.mode == "gpio":
            run_gpio_loop(cap, buttons, out_dir, args, recorder=recorder)
        else:
            run_keyboard_loop(cap, out_dir, args, recorder=recorder)
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
    finally:
        if recorder is not None:
            info = recorder.stop()
            print(
                f"Session video saved: {info['video']} "
                f"({info['frames']} frames @ {info['fps']} fps)",
                flush=True,
            )
        cap.release()
        if args.show:
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
