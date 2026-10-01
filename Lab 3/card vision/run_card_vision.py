#!/usr/bin/env python3
"""
CLI for the standalone Card Vision MVP.

Examples:
  python run_card_vision.py --image path/to/photo.jpg
  python run_card_vision.py --image path/to/photo.jpg --show --save-annotated out.jpg
  python run_card_vision.py --check-templates
  python run_card_vision.py --webcam
  python run_card_vision.py --webcam --camera 1 --interval 3
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import cv2

import Cards
import card_vision


def public_result(detections, verbose: bool):
    """Strip debug fields unless --verbose."""
    return card_vision.public_detections(detections, verbose=verbose)


def draw_detections(image, detections):
    """Draw compact card labels and centers on a copy of the image."""
    return card_vision.annotate_frame(image, detections)


def run_image(args):
    image = cv2.imread(args.image)
    if image is None:
        print(f"ERROR: could not read image: {args.image}", file=sys.stderr)
        return 1

    detections = card_vision.detect_cards(
        image,
        template_dir=args.templates,
        min_area=args.min_area,
        max_area=args.max_area,
        include_unknown=not args.skip_unknown,
    )
    result = public_result(detections, args.verbose)
    print(json.dumps({
        "detections": result,
        "zones": card_vision.assign_zones(detections),
    }, indent=2))

    annotated = draw_detections(image, detections)
    if args.save_annotated:
        card_vision.save_frame(annotated, args.save_annotated)
        print(f"Wrote annotated image: {args.save_annotated}", file=sys.stderr)

    if args.export_dir:
        exported = card_vision.export_capture(
            image,
            detections=detections,
            out_dir=args.export_dir,
            verbose=args.verbose,
        )
        print(
            f"Exported: {exported['image']} | {exported['annotated']} | {exported['json']}",
            file=sys.stderr,
        )

    if args.show:
        cv2.imshow("Card Vision MVP", annotated)
        print("Press any key in the image window to exit.", file=sys.stderr)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return 0


def run_check_templates(args):
    ranks, suits = card_vision.load_templates(args.templates)
    print(json.dumps({
        "templates": args.templates or card_vision.DEFAULT_TEMPLATE_DIR,
        "ranks": [item.name for item in ranks],
        "suits": [item.name for item in suits],
    }, indent=2))
    return 0


def run_webcam(args):
    try:
        cap = card_vision.open_usb_camera(
            camera_index=args.camera,
            width=args.width,
            height=args.height,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Preload templates once
    card_vision.load_templates(args.templates)

    recorder = None
    if args.record:
        recorder = card_vision.start_session_recording(
            out_dir=args.export_dir or card_vision.DEFAULT_EXPORT_DIR,
            fps=args.record_fps,
            draw_labels=not args.record_raw,
        )
        print(f"Recording session -> {recorder.path}", file=sys.stderr)

    interval = args.interval
    print(
        f"Webcam mode. Recognizing every {interval:.1f}s. "
        "Press 'q' to quit, 's' to export snapshot"
        + (", recording ON" if recorder else "")
        + ".",
        file=sys.stderr,
    )

    next_shot = 0.0
    detections = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("ERROR: failed to read frame from camera.", file=sys.stderr)
                break

            now = time.monotonic()
            if now >= next_shot:
                next_shot = now + interval
                detections = card_vision.detect_cards(
                    frame,
                    template_dir=args.templates,
                    min_area=args.min_area,
                    max_area=args.max_area,
                    include_unknown=not args.skip_unknown,
                )
                result = public_result(detections, args.verbose)
                print(json.dumps({
                    "detections": result,
                    "zones": card_vision.assign_zones(detections),
                }), flush=True)

            if recorder is not None:
                recorder.write(frame, detections=detections)

            annotated = draw_detections(frame, detections)
            cv2.imshow("Card Vision MVP", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                exported = card_vision.export_capture(
                    frame,
                    detections=detections,
                    out_dir=args.export_dir or card_vision.DEFAULT_EXPORT_DIR,
                    verbose=args.verbose,
                )
                print(
                    f"Exported snapshot: {exported['annotated']}",
                    file=sys.stderr,
                    flush=True,
                )
            if key == ord("q"):
                break
    finally:
        if recorder is not None:
            info = recorder.stop()
            print(
                f"Session video saved: {info['video']} "
                f"({info['frames']} frames @ {info['fps']} fps)",
                file=sys.stderr,
            )
        cap.release()
        cv2.destroyAllWindows()
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="Standalone Card Vision MVP (static image or USB webcam)."
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image", help="Path to a static test image")
    mode.add_argument("--webcam", action="store_true", help="Use USB webcam")
    mode.add_argument(
        "--check-templates",
        action="store_true",
        help="Load Card_Imgs and print the rank and suit names",
    )

    p.add_argument(
        "--templates",
        default=None,
        help="Directory of rank/suit templates (default: ./Card_Imgs)",
    )
    p.add_argument(
        "--camera",
        type=int,
        default=0,
        help="USB camera index for --webcam (default: 0)",
    )
    p.add_argument("--width", type=int, default=1280, help="Capture width")
    p.add_argument("--height", type=int, default=720, help="Capture height")
    p.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Seconds between recognitions in --webcam (default: 3)",
    )
    p.add_argument(
        "--min-area",
        type=int,
        default=None,
        help=f"Override min card contour area (default: {Cards.CARD_MIN_AREA})",
    )
    p.add_argument(
        "--max-area",
        type=int,
        default=None,
        help=f"Override max card contour area (default: {Cards.CARD_MAX_AREA})",
    )
    p.add_argument(
        "--skip-unknown",
        action="store_true",
        help="Omit detections that failed rank/suit matching",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Include rank/suit/diff debug fields in JSON output",
    )
    p.add_argument(
        "--show",
        action="store_true",
        help="Show annotated image window (--image mode)",
    )
    p.add_argument(
        "--save-annotated",
        default=None,
        help="Save annotated image to this path (--image mode)",
    )
    p.add_argument(
        "--export-dir",
        default=None,
        help="Export raw+annotated+JSON into this folder (demo bundle). "
        "In --webcam mode, press 's' to snapshot.",
    )
    p.add_argument(
        "--record",
        action="store_true",
        help="(--webcam) Record a session video until quit; saves under captures/",
    )
    p.add_argument(
        "--record-fps",
        type=float,
        default=10.0,
        help="Session recording FPS (default 10, lighter on Pi)",
    )
    p.add_argument(
        "--record-raw",
        action="store_true",
        help="Record raw frames without burning card labels into the video",
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.check_templates:
        return run_check_templates(args)
    if args.image:
        return run_image(args)
    if args.interval <= 0:
        print("ERROR: --interval must be greater than 0.", file=sys.stderr)
        return 1
    return run_webcam(args)


if __name__ == "__main__":
    raise SystemExit(main())
