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
import socket
import sys
import threading
import time

import cv2
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import Cards
import card_vision


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
        "zones": card_vision.assign_zones(detections),
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
    return payload["detections"]


def grab_fresh_frame(cap, flush_reads: int = 5):
    """Discard a few buffered frames so the capture is recent."""
    return card_vision.grab_frame(cap, flush_reads=flush_reads)


def _local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def overlay_frame(frame, detections, min_area, max_area):
    """Draw the background mark, card-shaped contours, and the latest names."""
    out = frame.copy()
    height, width = out.shape[:2]
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
    names = [str(item.get("card", "?")) for item in (detections or [])]
    banner = "result: " + (", ".join(names) if names else "none")
    cv2.putText(
        labeled, banner, (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA
    )
    cv2.putText(
        labeled, banner, (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA
    )
    return labeled


class BrowserPreview:
    """Serve the latest annotated frame as a browser MJPEG stream."""

    def __init__(self, port: int):
        self.port = port
        self._jpg = None
        self._lock = threading.Lock()
        self._httpd = None
        self._thread = None

    def update(self, frame) -> None:
        ok, encoded = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60]
        )
        if not ok:
            return
        with self._lock:
            self._jpg = encoded.tobytes()

    def latest(self):
        with self._lock:
            return self._jpg

    def start(self) -> str:
        preview = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header(
                    "Content-Type", "multipart/x-mixed-replace; boundary=frame"
                )
                self.end_headers()
                try:
                    while True:
                        jpg = preview.latest()
                        if jpg is None:
                            time.sleep(0.05)
                            continue
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                        )
                        time.sleep(0.05)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

            def log_message(self, format, *args):
                return

        try:
            self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as exc:
            raise RuntimeError(
                f"preview port {self.port} is in use ({exc}). "
                "Stop the old preview.py with Ctrl-C, then run this again."
            ) from exc
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{_local_ip()}:{self.port}"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()


def run_loop(cap, buttons: ButtonInputs, out_dir: str, args, recorder=None, preview=None):
    interval = args.interval
    next_shot = time.monotonic()
    latest = []
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

        if recorder is not None:
            recorder.write(frame)

        now = time.monotonic()
        if now >= next_shot:
            next_shot = now + interval
            if args.preview:
                fresh = frame
            else:
                fresh = grab_fresh_frame(cap)
                if fresh is None:
                    fresh = frame
            latest = capture_and_recognize(fresh, out_dir, args)

        view = None
        if args.preview or args.show:
            view = overlay_frame(frame, latest, args.min_area, args.max_area)
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
        if buttons.mode == "keyboard" and _keyboard_quit():
            print("Quit.", flush=True)
            break
        time.sleep(0.02)


def _keyboard_quit() -> bool:
    if os.name == "nt":
        import msvcrt
        if not msvcrt.kbhit():
            return False
        return msvcrt.getwch().lower() in ("q", "b")
    import select
    readable, _, _ = select.select([sys.stdin], [], [], 0)
    if not readable:
        return False
    return sys.stdin.readline().strip().lower() in ("q", "b", "quit", "exit")


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
