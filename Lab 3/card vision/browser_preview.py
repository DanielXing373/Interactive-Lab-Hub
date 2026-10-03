"""Serve the latest annotated camera frame as a browser MJPEG stream."""

from __future__ import annotations

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

import cv2


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


class BrowserPreview:
    """Serve the latest annotated frame as a browser MJPEG stream."""

    def __init__(self, port: int):
        self.port = port
        self._jpg: Optional[bytes] = None
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
                "Stop the other preview, then run this again."
            ) from exc
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{local_ip()}:{self.port}"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
