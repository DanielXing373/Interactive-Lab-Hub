#!/usr/bin/env python3
"""
Raspberry Pi card vision loop.

Opens the USB camera and recognizes cards on a timer. No button press is
required to take a picture. Button B (GPIO24) or q still quits.

  python3 pi_capture_test.py
  python3 pi_capture_test.py --interval 3 --camera 0
  python3 pi_capture_test.py --keyboard --interval 1 --preview
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
from browser_preview import BrowserPreview

import Cards
import card_vision
import zones


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
                    f"GPIO buttons: B=D{gpio_b} quits. Capture runs on a timer.",
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
            print("Keyboard mode: press q to quit. Capture runs on a timer.", flush=True)

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
    """Recognize one frame. Write files only when --save is set."""
    detections = card_vision.detect_cards(
        frame,
        template_dir=args.templates,
        min_area=args.min_area,
        max_area=args.max_area,
        include_unknown=not args.skip_unknown,
    )
    payload = {
        "detections": card_vision.public_detections(detections, verbose=args.verbose),
        "zones": card_vision.assign_zones(detections, image_height=frame.shape[0]),
    }
    print(json.dumps(payload), flush=True)
    if args.save:
        exported = card_vision.export_capture(
            frame,
            detections=detections,
            out_dir=out_dir,
            verbose=args.verbose,
        )
        print(f"Saved: {exported['json']}", flush=True)
    return detections


def grab_fresh_frame(cap, flush_reads: int = 5):
    """Discard a few buffered frames so the capture is recent."""
    return card_vision.grab_frame(cap, flush_reads=flush_reads)


def flip_frame(frame, mode: str):
    """Undo a mirrored camera so the rank sits in the top-left corner."""
    if frame is None or mode == "none":
        return frame
    if mode == "horizontal":
        return cv2.flip(frame, 1)
    if mode == "vertical":
        return cv2.flip(frame, 0)
    if mode == "both":
        return cv2.flip(frame, -1)
    return frame


RANK_NAMES = (
    "Ace", "Two", "Three", "Four", "Five", "Six", "Seven",
    "Eight", "Nine", "Ten", "Jack", "Queen", "King",
)


def first_query_card(frame, min_area, max_area):
    """Return the processed card for the largest accepted contour."""
    old_min, old_max = Cards.CARD_MIN_AREA, Cards.CARD_MAX_AREA
    if min_area is not None:
        Cards.CARD_MIN_AREA = int(min_area)
    if max_area is not None:
        Cards.CARD_MAX_AREA = int(max_area)
    try:
        pre = Cards.preprocess_image(frame)
        contours, flags = Cards.find_cards(pre)
        for index, flag in enumerate(flags):
            if flag == 1:
                return Cards.preprocess_card(contours[index], frame)
        return None
    except cv2.error:
        return None
    finally:
        Cards.CARD_MIN_AREA = old_min
        Cards.CARD_MAX_AREA = old_max


def save_rank_sample(frame, rank_name, min_area, max_area, dest_dir) -> bool:
    """Write this card's rank glyph over Card_Imgs/<Rank>.jpg."""
    query = first_query_card(frame, min_area, max_area)
    if query is None or len(query.rank_img) == 0:
        print("No rank crop to save. Wait for a green outline.", flush=True)
        return False
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, rank_name + ".jpg")
    if not cv2.imwrite(path, query.rank_img):
        print(f"Could not write {path}", flush=True)
        return False
    card_vision.clear_template_cache()
    print(f"Saved {rank_name} template: {path}", flush=True)
    return True


def make_corner_panel(frame, min_area, max_area):
    """Flatten the largest card and show the corner pixels used for recognition."""
    try:
        query = first_query_card(frame, min_area, max_area)
        if query is None:
            return None
        warp = query.warp
        if not hasattr(warp, "shape") or warp.size == 0:
            return None
        panel = cv2.cvtColor(warp, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(
            panel,
            (0, 0),
            (Cards.CORNER_WIDTH - 1, Cards.CORNER_HEIGHT - 1),
            (0, 0, 255),
            1,
        )
        crop_ok = len(query.rank_img) != 0 and len(query.suit_img) != 0
        note = "crop ok" if crop_ok else "crop empty"
        cv2.putText(
            panel,
            note,
            (4, 292),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
        corner = warp[0:Cards.CORNER_HEIGHT, 0:Cards.CORNER_WIDTH]
        corner_big = cv2.resize(corner, (128, 336), interpolation=cv2.INTER_NEAREST)
        corner_bgr = cv2.cvtColor(corner_big, cv2.COLOR_GRAY2BGR)
        canvas = np.zeros((336, 328, 3), dtype=np.uint8)
        canvas[0:300, 0:200] = panel
        canvas[:, 200:328] = corner_bgr
        return canvas
    except cv2.error:
        return None


def _status_lines(detections) -> list:
    """Top-left text for a one-card sweep: result, guess, and both diffs."""
    if not detections:
        return ["result: none"]
    lines = []
    for item in detections[:2]:
        card_name = str(item.get("card", "?"))
        guess_rank = item.get("rank_guess") or "?"
        guess_suit = item.get("suit_guess") or "?"
        shown = card_name if card_name != "Unknown" else ("?" + str(guess_rank))
        lines.append("result: %s   guess: %s of %s" % (shown, guess_rank, guess_suit))
        lines.append(
            "rank %s   second %s   suit %s"
            % (
                item.get("rank_diff", "?"),
                item.get("rank_second_diff", "?"),
                item.get("suit_diff", "?"),
            )
        )
    return lines


def overlay_frame(frame, detections, min_area, max_area, corner_panel=None):
    """Draw the background mark, card-shaped contours, and the latest names."""
    out = frame.copy()
    height, width = out.shape[:2]
    split_y = int(height * zones.HOLE_Y_FRACTION)
    cv2.line(out, (0, split_y), (width, split_y), (0, 255, 255), 2)
    cv2.putText(out, "board", (12, max(24, split_y - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(out, "pi hole", (12, min(height - 12, split_y + 28)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
    mark_x, mark_y = width // 2, max(1, height // 100)
    cv2.drawMarker(out, (mark_x, mark_y), (0, 0, 255), cv2.MARKER_CROSS, 40, 2)
    cv2.putText(
        out,
        "keep empty",
        (mark_x + 18, mark_y + 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )

    lo = Cards.CARD_MIN_AREA if min_area is None else int(min_area)
    hi = Cards.CARD_MAX_AREA if max_area is None else int(max_area)
    thresh = Cards.preprocess_image(frame)
    contours, hierarchy = Cards.find_contours(
        thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )
    if len(contours):
        order = sorted(
            range(len(contours)),
            key=lambda i: cv2.contourArea(contours[i]),
            reverse=True,
        )[:5]
        for index in order:
            size = cv2.contourArea(contours[index])
            peri = cv2.arcLength(contours[index], True)
            corners = len(cv2.approxPolyDP(contours[index], 0.01 * peri, True))
            parent = int(hierarchy[0][index][3])
            accepted = lo < size < hi and parent == -1 and corners == 4
            color = (0, 255, 0) if accepted else (0, 165, 255)
            cv2.drawContours(out, [contours[index]], -1, color, 2)

    labeled = card_vision.annotate_frame(out, detections or [])
    lines = _status_lines(detections)
    for index, line in enumerate(lines):
        origin = (12, 32 + index * 28)
        cv2.putText(
            labeled, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA
        )
        cv2.putText(
            labeled, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA
        )
    if corner_panel is not None:
        panel_h, panel_w = corner_panel.shape[:2]
        y0 = max(0, labeled.shape[0] - panel_h)
        x1 = min(labeled.shape[1], panel_w)
        h_fit = min(panel_h, labeled.shape[0] - y0)
        labeled[y0:y0 + h_fit, 0:x1] = corner_panel[0:h_fit, 0:x1]
    return labeled


def run_loop(cap, buttons: ButtonInputs, out_dir: str, args, recorder=None, preview=None):
    interval = args.interval
    next_shot = time.monotonic()
    latest = []
    corner_panel = None
    print(
        f"Recognizing every {interval:.1f}s. Quit with button B, q, or Ctrl-C.",
        flush=True,
    )
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("ERROR: camera read failed.", file=sys.stderr, flush=True)
            time.sleep(0.2)
            continue
        frame = flip_frame(frame, args.flip)

        if recorder is not None:
            recorder.write(frame)

        now = time.monotonic()
        if now >= next_shot:
            next_shot = now + interval
            if args.preview:
                fresh = frame
            else:
                fresh = flip_frame(grab_fresh_frame(cap), args.flip)
                if fresh is None:
                    fresh = frame
            latest = capture_and_recognize(fresh, out_dir, args)
            if args.preview or args.show:
                corner_panel = make_corner_panel(fresh, args.min_area, args.max_area)

        view = None
        if args.preview or args.show:
            view = overlay_frame(
                frame, latest, args.min_area, args.max_area, corner_panel=corner_panel
            )
        if preview is not None and view is not None:
            preview.update(view)

        if args.show and view is not None:
            cv2.imshow("Card Vision Pi (q = quit)", view)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("b")):
                print("Quit.", flush=True)
                break

        buttons.poll()
        if buttons.b_pressed:
            print("Quit (button B).", flush=True)
            break
        if buttons.mode == "keyboard":
            command = _keyboard_command()
            if command in ("q", "b", "quit", "exit"):
                print("Quit.", flush=True)
                break
            if command == "s":
                if not args.save_rank:
                    print("Pass --save-rank Queen (or Jack, Ten) before typing s.", flush=True)
                else:
                    fresh = frame
                    save_rank_sample(
                        fresh,
                        args.save_rank,
                        args.min_area,
                        args.max_area,
                        template_directory(args),
                    )
        time.sleep(0.02)


def _keyboard_command():
    if os.name == "nt":
        import msvcrt
        if not msvcrt.kbhit():
            return None
        return msvcrt.getwch().lower()
    import select
    readable, _, _ = select.select([sys.stdin], [], [], 0)
    if not readable:
        return None
    return sys.stdin.readline().strip().lower()


def template_directory(args) -> str:
    if args.templates:
        return args.templates
    return os.path.join(os.path.dirname(os.path.abspath(card_vision.__file__)), "Card_Imgs")


def canonical_rank(name: str):
    for rank in RANK_NAMES:
        if rank.lower() == name.lower():
            return rank
    return None


def build_parser():
    p = argparse.ArgumentParser(
        description="Pi USB webcam capture + card recognition (MiniPiTFT A/B buttons)."
    )
    p.add_argument("--camera", type=int, default=0, help="USB camera index (default 0)")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Seconds between recognitions (default: 3)",
    )
    p.add_argument(
        "--save",
        action="store_true",
        help="Write each recognition to ./captures as jpg and json",
    )
    p.add_argument(
        "--out-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures"),
        help="Directory for saved photos / JSON (default: ./captures)",
    )
    p.add_argument("--templates", default=None, help="Rank/suit template directory")
    p.add_argument("--min-area", type=int, default=None)
    p.add_argument("--max-area", type=int, default=None)
    p.add_argument("--skip-unknown", action="store_true")
    p.add_argument(
        "--save-rank",
        default=None,
        help="Save the current card's rank glyph when you type s. Example: Queen",
    )
    p.add_argument(
        "--flip",
        choices=("horizontal", "vertical", "both", "none"),
        default="horizontal",
        help="Flip the camera before recognition (default: horizontal, for a mirrored webcam)",
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--show",
        action="store_true",
        help="Show OpenCV preview window (needs display)",
    )
    p.add_argument(
        "--preview",
        action="store_true",
        help="Serve a browser preview with contours and the latest card names",
    )
    p.add_argument(
        "--preview-port",
        type=int,
        default=8080,
        help="Browser preview port (default 8080)",
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

    if args.interval <= 0:
        print("ERROR: --interval must be greater than 0.", file=sys.stderr)
        return 1
    if args.save_rank:
        rank_name = canonical_rank(args.save_rank)
        if rank_name is None:
            print(
                "ERROR: --save-rank must be one of: " + ", ".join(RANK_NAMES),
                file=sys.stderr,
            )
            return 1
        args.save_rank = rank_name

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
    print(f"Camera flip: {args.flip}", flush=True)
    if args.save_rank:
        print(
            f"Hold a {args.save_rank}. Type s and press Enter to save its rank template.",
            flush=True,
        )

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

    preview = None
    if args.preview:
        preview = BrowserPreview(args.preview_port)
        try:
            url = preview.start()
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            cap.release()
            return 1
        print(f"Preview: {url}", flush=True)
        print("Green outline = card shape. Top-left text = latest recognition.", flush=True)

    try:
        run_loop(cap, buttons, out_dir, args, recorder=recorder, preview=preview)
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
    finally:
        if preview is not None:
            preview.stop()
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
